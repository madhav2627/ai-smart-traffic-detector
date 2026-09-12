"""
AI Intelligent Traffic Monitoring - UVH-26 Indian Traffic Edition

This version uses the free IISc UVH-26 YOLOv11-S model bundled as
vehicle_traffic.pt. The model has 14 Indian-traffic classes; inference
normalizes them to the five dashboard classes used by this project:

    car, motorcycle, auto, bus, truck

Pipeline:
    video/CCTV -> UVH-26 detection -> class mapping -> ByteTrack ->
    unique vehicle tracking -> trajectory direction -> traffic density -> relative speed
    -> annotated video + JSON report

Optimized for high throughput:
- GPU acceleration (CUDA)
- Dynamic resolution management (HD web-optimized output)
- Smart frame cadence for fast tracking without dropping video frames
- Hardware-accelerated H.264 web encoding
"""

from pathlib import Path
from collections import defaultdict, deque, Counter
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np
import torch
from ultralytics import YOLO

# ============================================================
# ARGUMENTS & PATH RESOLUTION
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent

parser = argparse.ArgumentParser(description="UVH-26 AI Traffic Monitor")
parser.add_argument("--input", "-i", default="video.mp4", help="Path to input video")
parser.add_argument("--output", "--output-video", "-o", default="traffic_output.mp4", help="Path to output video")
parser.add_argument("--report", "--output-report", "-r", default="traffic_report.json", help="Path to JSON report")
parser.add_argument("--model", "-m", default=None, help="Path to UVH-26 model weights")
parser.add_argument("--tracker", default="bytetrack.yaml", help="Tracker config")
parser.add_argument("--conf", type=float, default=0.20, help="Confidence threshold")
parser.add_argument("--iou", type=float, default=0.50, help="IOU threshold")
parser.add_argument("--imgsz", type=int, default=512, help="YOLO image size (512 for optimal throughput)")
parser.add_argument("--stride", type=int, default=None, help="Inference frame stride (e.g. 2 for 2x speed)")
parser.add_argument("--max-dim", type=int, default=1280, help="Maximum video dimension for output")
parser.add_argument("--device", default=None, help="Device to run inference on (e.g. 0, cuda, cpu)")
parser.add_argument("--session-id", default=None, help="Analysis session identifier")
args, _ = parser.parse_known_args()

SESSION_ID = args.session_id or f"sess_{int(time.time())}"

# Input video resolution
input_path_candidate = Path(args.input)
if not input_path_candidate.is_absolute():
    if input_path_candidate.exists():
        input_path_candidate = input_path_candidate.resolve()
    elif (SCRIPT_DIR / input_path_candidate).exists():
        input_path_candidate = (SCRIPT_DIR / input_path_candidate).resolve()
VIDEO_PATH = str(input_path_candidate)

# Output video and report paths
out_video_candidate = Path(args.output)
if not out_video_candidate.is_absolute():
    out_video_candidate = (Path.cwd() / out_video_candidate).resolve()
OUTPUT_PATH = str(out_video_candidate)

out_report_candidate = Path(args.report)
if not out_report_candidate.is_absolute():
    out_report_candidate = (Path.cwd() / out_report_candidate).resolve()
REPORT_PATH = str(out_report_candidate)

# Model path resolution
if args.model:
    model_candidate = Path(args.model)
    if not model_candidate.is_absolute() and (SCRIPT_DIR / model_candidate).exists():
        model_candidate = SCRIPT_DIR / model_candidate
else:
    model_candidate = SCRIPT_DIR / "vehicle_traffic.pt"
MODEL_PATH = str(model_candidate.resolve() if model_candidate.exists() else model_candidate)

# Hardware acceleration setup
cuda_avail = torch.cuda.is_available()
if args.device is not None:
    DEVICE = args.device
else:
    DEVICE = 0 if cuda_avail else "cpu"

# Ensure output directories exist
out_video_candidate.parent.mkdir(parents=True, exist_ok=True)
out_report_candidate.parent.mkdir(parents=True, exist_ok=True)

# Processing parameters
CONFIDENCE = args.conf
COUNT_CONFIDENCE = 0.30
IOU = args.iou
IMG_SIZE = args.imgsz
TRACKER = args.tracker
MAX_DIM = args.max_dim

# Tracking parameters
MIN_BOX_AREA_RATIO = 0.00025
CONFIRM_FRAMES = 2
TRACK_HISTORY = 30
METERS_PER_PIXEL = 0.0

# ============================================================
# UVH-26 -> dashboard class mapping
# ============================================================
UVH26_TO_APP = {
    "Hatchback": "car",
    "Sedan": "car",
    "SUV": "car",
    "MUV": "car",
    "Bus": "bus",
    "Truck": "truck",
    "Three-wheeler": "auto",
    "Two-wheeler": "motorcycle",
    "LCV": "truck",
    "Mini-bus": "bus",
    "tempo-traveller": "bus",
    "bicycle": "motorcycle",
    "Van": "car",
    "Others": "car",
}

APP_CLASSES = ("car", "motorcycle", "auto", "bus", "truck")

DISPLAY_LABELS = {
    "car": "CAR",
    "motorcycle": "MOTORCYCLE",
    "auto": "AUTO-RICKSHAW",
    "bus": "BUS",
    "truck": "TRUCK",
}

COLORS = {
    "car": (255, 200, 0),
    "motorcycle": (0, 220, 255),
    "auto": (0, 165, 255),
    "bus": (255, 80, 180),
    "truck": (180, 80, 255),
}


def normalize_source_label(label: str) -> str:
    """Map exact UVH-26 names plus minor formatting variants."""
    clean = str(label).strip().lower().replace("_", " ")
    aliases = {
        "hatchback": "Hatchback",
        "sedan": "Sedan",
        "suv": "SUV",
        "muv": "MUV",
        "bus": "Bus",
        "truck": "Truck",
        "three-wheeler": "Three-wheeler",
        "three wheeler": "Three-wheeler",
        "auto": "Three-wheeler",
        "autorickshaw": "Three-wheeler",
        "auto-rickshaw": "Three-wheeler",
        "two-wheeler": "Two-wheeler",
        "two wheeler": "Two-wheeler",
        "motorcycle": "Two-wheeler",
        "motorbike": "Two-wheeler",
        "bike": "Two-wheeler",
        "bicycle": "bicycle",
        "lcv": "LCV",
        "mini-bus": "Mini-bus",
        "mini bus": "Mini-bus",
        "van": "Van",
        "tempo-traveller": "tempo-traveller",
        "tempo traveller": "tempo-traveller",
        "others": "Others",
        "other": "Others",
    }
    return aliases.get(clean, str(label))


def app_label_from_source(label: str):
    return UVH26_TO_APP.get(normalize_source_label(label))


def traffic_level(active_count: int) -> str:
    if active_count <= 8:
        return "LOW"
    if active_count <= 20:
        return "MEDIUM"
    if active_count <= 35:
        return "HIGH"
    return "SEVERE"


def estimate_speed(history, fps):
    if len(history) < 2 or fps <= 0:
        return 0.0, None
    xs = np.asarray([p[0] for p in history], dtype=float)
    ys = np.asarray([p[1] for p in history], dtype=float)
    frames = np.asarray([p[2] for p in history], dtype=float)
    times = (frames - frames[0]) / fps
    if times[-1] <= times[0]:
        return 0.0, None
    vx = np.polyfit(times, xs, 1)[0]
    vy = np.polyfit(times, ys, 1)[0]
    px_per_sec = float(np.hypot(vx, vy))
    kmh = px_per_sec * METERS_PER_PIXEL * 3.6 if METERS_PER_PIXEL > 0 else None
    return px_per_sec, kmh


def majority_label(label_history):
    if not label_history:
        return "unknown", 0.0
    label = Counter(lbl for lbl, _ in label_history).most_common(1)[0][0]
    confs = [c for lbl, c in label_history if lbl == label]
    return label, float(sum(confs) / len(confs))


# ============================================================
# LOAD MODEL & ACCELERATION
# ============================================================
print(f"[TrafficAI] Loading UVH-26: {MODEL_PATH}", flush=True)
model_file = Path(MODEL_PATH)
if not model_file.exists():
    raise FileNotFoundError(
        f"{MODEL_PATH} was not found. This package expects the bundled "
        "UVH-26-MV-YOLOv11-S weights renamed to vehicle_traffic.pt."
    )
model = YOLO(str(model_file))
if cuda_avail and DEVICE != "cpu":
    model.to("cuda")
    torch.backends.cudnn.benchmark = True
    print(f"[TrafficAI] Acceleration: NVIDIA GPU ({torch.cuda.get_device_name(0)})", flush=True)
else:
    print(f"[TrafficAI] Running on device: {DEVICE}", flush=True)

# ============================================================
# VIDEO SETUP & RESIZING FOR HIGH SPEED
# ============================================================
print(f"[TrafficAI] Input received: {VIDEO_PATH} (Session: {SESSION_ID})", flush=True)
cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    raise RuntimeError(f"Could not open video: {VIDEO_PATH}")

fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

# Scale resolution down to standard HD (e.g. 1280 max dimension) for web speed
scale = min(1.0, float(MAX_DIM) / max(orig_w, orig_h)) if max(orig_w, orig_h) > MAX_DIM else 1.0
width = int(orig_w * scale)
width = width if width % 2 == 0 else width - 1
height = int(orig_h * scale)
height = height if height % 2 == 0 else height - 1

if args.stride is not None:
    frame_stride = max(1, args.stride)
else:
    frame_stride = 1 if (total_frames <= 600 or fps < 24) else 2

frame_area = float(width * height)
min_box_area = MIN_BOX_AREA_RATIO * frame_area

raw_video_path = str(out_video_candidate.with_name(f"temp_raw_{out_video_candidate.name}"))

print(f"[TrafficAI] Pass 1: Tracking vehicles on {total_frames} frames...", flush=True)

# ============================================================
# PASS 1: DETECTION & TRACK REGISTRATION
# ============================================================
unique_vehicle_classes = {}
tracks = defaultdict(lambda: deque(maxlen=TRACK_HISTORY))
label_history = defaultdict(lambda: deque(maxlen=TRACK_HISTORY))
track_frame_counts = Counter()
last_seen = {}
vehicles_detail = {}
per_frame_draw_items = []
per_frame_active_counts = []
frame_number = 0
start_time = time.time()
last_pct = -1

cached_draw_items = []
current_active_count = 0

while True:
    ok, frame = cap.read()
    if not ok:
        break
    frame_number += 1

    if scale < 1.0:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    if total_frames > 0:
        pct = int((frame_number / total_frames) * 100)
        if pct != last_pct and pct % 10 == 0:
            last_pct = pct
            elapsed_so_far = max(time.time() - start_time, 0.01)
            fps_so_far = frame_number / elapsed_so_far
            print(f"[TrafficAI] Analyzing frames: {pct}% ({frame_number}/{total_frames}) [{fps_so_far:.1f} fps]", flush=True)

    should_infer = (frame_number % frame_stride == 0) or (frame_number == 1)

    if should_infer:
        result = model.track(
            source=frame,
            persist=True,
            tracker=TRACKER,
            conf=CONFIDENCE,
            iou=IOU,
            imgsz=IMG_SIZE,
            device=DEVICE,
            verbose=False,
        )[0]

        active_ids = set()
        cached_draw_items = []

        if result.boxes is not None and len(result.boxes) > 0:
            boxes = result.boxes
            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            class_ids = boxes.cls.cpu().numpy().astype(int)
            ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else np.full(len(xyxy), -1)

            for box, conf, class_id, track_id in zip(xyxy, confs, class_ids, ids):
                x1, y1, x2, y2 = map(int, box)
                area = max(0, x2 - x1) * max(0, y2 - y1)
                if area < min_box_area:
                    continue

                source_name = result.names.get(int(class_id), str(class_id))
                app_label = app_label_from_source(source_name)
                if app_label is None:
                    continue

                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)

                if track_id >= 0:
                    active_ids.add(track_id)
                    last_seen[track_id] = frame_number
                    track_frame_counts[track_id] += 1
                    tracks[track_id].append((cx, cy, frame_number))
                    label_history[track_id].append((app_label, float(conf)))
                    stable_label, stable_conf = majority_label(label_history[track_id])
                    unique_vehicle_classes[track_id] = stable_label

                    px_speed, kmh = estimate_speed(tracks[track_id], fps)
                    det_dir = None
                    if len(tracks[track_id]) >= 2:
                        y_start = tracks[track_id][0][1]
                        y_curr = tracks[track_id][-1][1]
                        dy = y_curr - y_start
                        if abs(dy) >= 3:
                            det_dir = "DOWN" if dy > 0 else "UP"

                    vehicles_detail[track_id] = {
                        "id": int(track_id),
                        "track_id": int(track_id),
                        "class": stable_label,
                        "type": stable_label,
                        "conf": round(float(stable_conf), 3),
                        "direction": det_dir or "UNKNOWN",
                        "status": "TRACKED",
                        "frames_tracked": int(track_frame_counts[track_id]),
                        "color": "Silver",
                        "plate": "N/A",
                    }
                else:
                    stable_label, stable_conf = app_label, float(conf)
                    px_speed, kmh = 0.0, None

                color = COLORS.get(stable_label, (200, 200, 200))
                speed_text = f" {kmh:.1f}km/h" if kmh is not None else f" {px_speed:.0f}px/s"
                id_text = f"ID:{track_id}" if track_id >= 0 else "ID:-"
                text = f"{id_text} {DISPLAY_LABELS[stable_label]} {stable_conf:.0%}{speed_text}"

                cached_draw_items.append((x1, y1, x2, y2, cx, cy, color, text, track_id))

        current_active_count = len(active_ids)

    per_frame_draw_items.append(list(cached_draw_items))
    per_frame_active_counts.append(current_active_count)

cap.release()

# ============================================================
# DERIVE ONE AUTHORITATIVE SESSION RESULT
# ============================================================
# Filter unique vehicles by persistence across video
cars_candidates = sorted([tid for tid, lbl in unique_vehicle_classes.items() if lbl == 'car'], key=lambda tid: track_frame_counts[tid], reverse=True)
motos_candidates = sorted([tid for tid, lbl in unique_vehicle_classes.items() if lbl == 'motorcycle'], key=lambda tid: track_frame_counts[tid], reverse=True)
autos_candidates = sorted([tid for tid, lbl in unique_vehicle_classes.items() if lbl == 'auto'], key=lambda tid: track_frame_counts[tid], reverse=True)
buses_candidates = sorted([tid for tid, lbl in unique_vehicle_classes.items() if lbl == 'bus'], key=lambda tid: track_frame_counts[tid], reverse=True)
trucks_candidates = sorted([tid for tid, lbl in unique_vehicle_classes.items() if lbl == 'truck'], key=lambda tid: track_frame_counts[tid], reverse=True)

# Keep every persistent tracked vehicle. There are intentionally NO line-crossing
# rules and NO artificial per-class caps. A track must be seen on at least
# CONFIRM_FRAMES inference frames to avoid counting one-frame tracker noise.
confirmed_track_ids = {
    tid for tid, frame_count in track_frame_counts.items()
    if frame_count >= CONFIRM_FRAMES and tid in unique_vehicle_classes
}

target_counts = {
    app_class: sum(1 for tid in confirmed_track_ids if unique_vehicle_classes.get(tid) == app_class)
    for app_class in APP_CLASSES
}
selected_track_ids = confirmed_track_ids
authoritative_total = len(selected_track_ids)

final_vehicles_detail = []
idx = 1
for tid in sorted(selected_track_ids):
    if tid in vehicles_detail:
        v = dict(vehicles_detail[tid])
        v["id"] = idx
        v["status"] = "TRACKED"
        final_vehicles_detail.append(v)
        idx += 1

print(f"[TrafficAI] Authoritative session unique vehicles established: {authoritative_total}", flush=True)

# ============================================================
# PASS 2: RENDER AUTHORITATIVE OVERLAY HUD & BOUNDING BOXES
# ============================================================
print(f"[TrafficAI] Pass 2: Rendering video with authoritative session HUD...", flush=True)
cap2 = cv2.VideoCapture(VIDEO_PATH)
fourcc = cv2.VideoWriter_fourcc(*"mp4v")
writer = cv2.VideoWriter(raw_video_path, fourcc, fps, (width, height))
if not writer.isOpened():
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(raw_video_path, fourcc, fps, (width, height))

frame_idx = 0
while True:
    ok, frame = cap2.read()
    if not ok or frame_idx >= len(per_frame_draw_items):
        break

    if scale < 1.0:
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

    # Draw detected bounding boxes
    for item in per_frame_draw_items[frame_idx]:
        x1, y1, x2, y2, cx, cy, color, text, tid = item
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, text, (x1, max(22, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 2)
        cv2.circle(frame, (cx, cy), 3, color, -1)

    # Render Authoritative Session HUD Overlay uniformly on every frame
    cv2.rectangle(frame, (8, 8), (420, 275), (15, 20, 28), -1)
    cv2.rectangle(frame, (8, 8), (420, 275), (40, 55, 75), 1)

    curr_act = per_frame_active_counts[frame_idx]
    curr_lvl = traffic_level(curr_act)

    overlay = [
        f"SESSION      : {SESSION_ID}",
        f"CAR          : {target_counts['car']}",
        f"MOTORCYCLE   : {target_counts['motorcycle']}",
        f"AUTO-RICKSHAW: {target_counts['auto']}",
        f"BUS          : {target_counts['bus']}",
        f"TRUCK        : {target_counts['truck']}",
        f"TOTAL UNIQUE : {authoritative_total}",
        f"ACTIVE NOW   : {curr_act} ({curr_lvl})",
    ]
    y = 32
    for line in overlay:
        text_color = (240, 245, 255)
        if "TOTAL UNIQUE" in line:
            text_color = (0, 255, 200)
        elif "ACTIVE NOW" in line:
            text_color = (100, 200, 255)
        elif "SESSION" in line:
            text_color = (160, 175, 200)
        cv2.putText(frame, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.48, text_color, 2)
        y += 28

    writer.write(frame)
    frame_idx += 1

cap2.release()
writer.release()
cv2.destroyAllWindows()

# ============================================================
# VIDEO POST-PROCESSING (Hardware H.264 Re-encode)
# ============================================================
ffmpeg_bin = shutil.which("ffmpeg")
if ffmpeg_bin and Path(raw_video_path).exists() and Path(raw_video_path).stat().st_size > 0:
    print(f"[TrafficAI] Re-encoding web-compatible H.264 video...", flush=True)
    temp_h264 = str(out_video_candidate.with_name(f"h264_{out_video_candidate.name}"))
    
    cmd_nvenc = [
        ffmpeg_bin, "-y",
        "-i", raw_video_path,
        "-c:v", "h264_nvenc",
        "-preset", "p1",
        "-cq", "24",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        temp_h264,
    ]
    cmd_cpu = [
        ffmpeg_bin, "-y",
        "-i", raw_video_path,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        temp_h264,
    ]
    
    encoded = False
    if cuda_avail:
        try:
            p_nvenc = subprocess.run(cmd_nvenc, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if p_nvenc.returncode == 0 and Path(temp_h264).exists() and Path(temp_h264).stat().st_size > 0:
                shutil.move(temp_h264, OUTPUT_PATH)
                encoded = True
                print(f"[TrafficAI] Output created: {OUTPUT_PATH} (NVENC H.264 Web-Ready)", flush=True)
        except Exception:
            pass

    if not encoded:
        try:
            p_cpu = subprocess.run(cmd_cpu, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if p_cpu.returncode == 0 and Path(temp_h264).exists() and Path(temp_h264).stat().st_size > 0:
                shutil.move(temp_h264, OUTPUT_PATH)
                encoded = True
                print(f"[TrafficAI] Output created: {OUTPUT_PATH} (CPU H.264 Web-Ready)", flush=True)
        except Exception as e:
            print(f"[TrafficAI] FFmpeg warning: {e}", flush=True)

    if not encoded:
        shutil.move(raw_video_path, OUTPUT_PATH)
        print(f"[TrafficAI] Output created: {OUTPUT_PATH} (Raw output)", flush=True)
    else:
        try:
            Path(raw_video_path).unlink(missing_ok=True)
        except Exception:
            pass
else:
    if Path(raw_video_path).exists():
        shutil.move(raw_video_path, OUTPUT_PATH)
    print(f"[TrafficAI] Output created: {OUTPUT_PATH}", flush=True)

# ============================================================
# REPORT GENERATION (ONE AUTHORITATIVE SESSION RESULT)
# ============================================================
elapsed = max(time.time() - start_time, 0.001)
avg_active = float(np.mean(per_frame_active_counts)) if per_frame_active_counts else 0.0
peak_active = int(max(per_frame_active_counts)) if per_frame_active_counts else 0

speed_values = []
for tid in selected_track_ids:
    if tid in tracks:
        px, _ = estimate_speed(tracks[tid], fps)
        if px > 0:
            speed_values.append(px)
avg_px_speed = float(np.mean(speed_values)) if speed_values else 0.0
avg_kmh = avg_px_speed * METERS_PER_PIXEL * 3.6 if METERS_PER_PIXEL > 0 else None

direction_counts = Counter()
for v in final_vehicles_detail:
    if v.get("direction") in ("UP", "DOWN"):
        direction_counts[v["direction"]] += 1
# Do not fabricate directions when the video does not provide enough motion.
# Vehicles without a reliable direction remain UNKNOWN and are reported separately.

video_dur = round(float(total_frames / fps), 2) if fps > 0 and total_frames > 0 else 0.0

report = {
    "session_id": SESSION_ID,
    "video": VIDEO_PATH,
    "model": MODEL_PATH,
    "model_source": "IISc UVH-26 YOLOv11-S",
    "frames_processed": frame_number,
    "processing_time_seconds": round(elapsed, 2),
    "analysis_duration": round(elapsed, 2),
    "video_duration": video_dur,
    "processing_fps": round(frame_number / elapsed, 2),
    "total_unique": authoritative_total,
    "total_vehicles": authoritative_total,
    "total_count": authoritative_total,
    "cars": int(target_counts["car"]),
    "motorcycles": int(target_counts["motorcycle"]),
    "auto_rickshaws": int(target_counts["auto"]),
    "buses": int(target_counts["bus"]),
    "trucks": int(target_counts["truck"]),
    "active_now": int(per_frame_active_counts[-1]) if per_frame_active_counts else 0,
    "vehicle_counts": {
        "car": int(target_counts["car"]),
        "motorcycle": int(target_counts["motorcycle"]),
        "auto": int(target_counts["auto"]),
        "auto_rickshaw": int(target_counts["auto"]),
        "bus": int(target_counts["bus"]),
        "truck": int(target_counts["truck"]),
    },
    "vehicles": {
        "total": authoritative_total,
        "car": int(target_counts["car"]),
        "motorcycle": int(target_counts["motorcycle"]),
        "auto": int(target_counts["auto"]),
        "auto_rickshaw": int(target_counts["auto"]),
        "bus": int(target_counts["bus"]),
        "truck": int(target_counts["truck"]),
    },
    "direction": {
        "up": int(direction_counts["UP"]),
        "down": int(direction_counts["DOWN"]),
    },
    "direction_counts": {
        "UP": int(direction_counts["UP"]),
        "DOWN": int(direction_counts["DOWN"]),
        "UNKNOWN": max(0, authoritative_total - int(direction_counts["UP"]) - int(direction_counts["DOWN"])),
    },
    "traffic_density": {
        "average_active": round(avg_active, 2),
        "peak_active": peak_active,
        "level": traffic_level(round(avg_active)),
    },
    "traffic": {
        "density": traffic_level(round(avg_active)),
        "average_active_vehicles": round(avg_active, 2),
        "peak_active_vehicles": peak_active,
    },
    "speed": {
        "average_pixels_per_second": round(avg_px_speed, 2),
        "average_kmh": round(avg_kmh, 2) if avg_kmh is not None else None,
        "real_kmh_enabled": METERS_PER_PIXEL > 0,
    },
    "relative_speed": round(avg_px_speed, 2),
    "configuration": {
        "tracker": TRACKER,
        "detect_confidence": CONFIDENCE,
        "count_confidence": COUNT_CONFIDENCE,
        "image_size": IMG_SIZE,
        "meters_per_pixel": METERS_PER_PIXEL,
        "frame_stride": frame_stride,
    },
    "uvh26_class_mapping": UVH26_TO_APP,
    "vehicles_detail": final_vehicles_detail,
}

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2)

print(f"[TrafficAI] Report created: {REPORT_PATH}", flush=True)
print(f"\n========== UVH-26 TRAFFIC REPORT (SESSION: {SESSION_ID}) ==========", flush=True)
for name in APP_CLASSES:
    print(f"{DISPLAY_LABELS[name]:14}: {target_counts[name]}", flush=True)
print(f"{'TOTAL UNIQUE':14}: {authoritative_total}", flush=True)
final_active_now = int(per_frame_active_counts[-1]) if per_frame_active_counts else 0
print(f"ACTIVE NOW     : {final_active_now} (AVG: {avg_active:.1f})", flush=True)
print(f"TRAFFIC LEVEL  : {traffic_level(round(avg_active))}", flush=True)
print(f"AVG SPEED      : {avg_px_speed:.1f} px/s", flush=True)
print(f"Output video   : {OUTPUT_PATH}", flush=True)
print(f"JSON report    : {REPORT_PATH}", flush=True)
print(f"[TrafficAI] Processing complete ({round(elapsed, 1)}s @ {round(frame_number / elapsed, 1)} fps)", flush=True)

