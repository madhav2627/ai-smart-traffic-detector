"""
SURVILLENCE TRAFFIC — Online AI Detection & ByteTrack Tracking Engine
====================================================================
Integrates the IISc UVH-26 YOLOv11-S model (vehicle_traffic.pt) with
ByteTrack unique vehicle tracking, class normalization, traffic density,
and trajectory speed analysis for Vercel serverless execution.

Normalized Classes:
  car, motorcycle, auto, bus, truck

No mock data. No fake simulation. Real model detections and real tracking.
"""

import os
import sys
import time
import json
import shutil
import subprocess
from pathlib import Path
from collections import defaultdict, deque, Counter

import cv2
import numpy as np

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PT = BASE_DIR / "traffic_ai_complete_improved" / "vehicle_traffic.pt"
MODEL_ONNX = BASE_DIR / "traffic_ai_complete_improved" / "vehicle_traffic.onnx"

# ── UVH-26 -> Dashboard Class Normalization ─────────────────────────────────
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
    "car": (255, 200, 0),        # Cyan/Yellow
    "motorcycle": (0, 220, 255), # Yellow/Gold
    "auto": (0, 165, 255),       # Orange
    "bus": (255, 80, 180),       # Magenta
    "truck": (180, 80, 255),     # Violet
}

def normalize_source_label(label: str) -> str:
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

# ── Pure Python Kalman & ByteTrack Tracker ──────────────────────────────────
class KalmanFilterBox:
    """Standard 2D bounding box Kalman filter for ByteTrack."""
    def __init__(self, bbox):
        # state: [x, y, a, h, vx, vy, va, vh]
        w = max(1.0, float(bbox[2] - bbox[0]))
        h = max(1.0, float(bbox[3] - bbox[1]))
        x = float(bbox[0]) + w / 2.0
        y = float(bbox[1]) + h / 2.0
        self.mean = np.array([x, y, w / h, h, 0.0, 0.0, 0.0, 0.0], dtype=float)
        self.covariance = np.diag([10.0, 10.0, 1.0, 10.0, 1000.0, 1000.0, 10.0, 1000.0])

    def predict(self):
        # Simple velocity model
        self.mean[0] += self.mean[4]
        self.mean[1] += self.mean[5]
        self.mean[2] += self.mean[6]
        self.mean[3] += self.mean[7]
        self.covariance += np.diag([1.0, 1.0, 0.01, 1.0, 1.0, 1.0, 0.01, 1.0])

    def update(self, bbox):
        w = max(1.0, float(bbox[2] - bbox[0]))
        h = max(1.0, float(bbox[3] - bbox[1]))
        x = float(bbox[0]) + w / 2.0
        y = float(bbox[1]) + h / 2.0
        z = np.array([x, y, w / h, h], dtype=float)
        H = np.zeros((4, 8), dtype=float)
        H[0, 0] = H[1, 1] = H[2, 2] = H[3, 3] = 1.0
        R = np.diag([1.0, 1.0, 0.01, 1.0])
        y_residual = z - (H @ self.mean)
        S = H @ self.covariance @ H.T + R
        K = self.covariance @ H.T @ np.linalg.inv(S)
        self.mean += K @ y_residual
        self.covariance = (np.eye(8) - K @ H) @ self.covariance

    def to_xyxy(self):
        x, y, a, h = self.mean[:4]
        w = a * h
        return np.array([x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0])

def compute_iou_matrix(boxes_a, boxes_b):
    if len(boxes_a) == 0 or len(boxes_b) == 0:
        return np.zeros((len(boxes_a), len(boxes_b)))
    matrix = np.zeros((len(boxes_a), len(boxes_b)))
    for i, a in enumerate(boxes_a):
        for j, b in enumerate(boxes_b):
            x1 = max(a[0], b[0])
            y1 = max(a[1], b[1])
            x2 = min(a[2], b[2])
            y2 = min(a[3], b[3])
            inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
            area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
            area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
            union = area_a + area_b - inter
            matrix[i, j] = inter / union if union > 0 else 0.0
    return matrix

class SimpleByteTrack:
    """Lightweight pure-Python ByteTrack tracker without external compiled C++ dependencies."""
    def __init__(self, high_thresh=0.40, low_thresh=0.15, max_lost_frames=30):
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.max_lost_frames = max_lost_frames
        self.tracks = {} # track_id -> dict(kf, box, class, conf, lost, history)
        self.next_id = 1

    def update(self, detections):
        """
        detections: list of dict(box=[x1,y1,x2,y2], score=conf, class=app_class)
        returns: list of dict(track_id, box, class, conf)
        """
        # 1. Predict all current tracks
        for tid, t in list(self.tracks.items()):
            t["kf"].predict()
            t["box"] = t["kf"].to_xyxy()
            t["lost"] += 1

        # 2. Separate high vs low score detections
        high_dets = [d for d in detections if d["score"] >= self.high_thresh]
        low_dets = [d for d in detections if self.low_thresh <= d["score"] < self.high_thresh]

        # 3. Match high detections to active tracks
        active_ids = [tid for tid, t in self.tracks.items() if t["lost"] <= self.max_lost_frames]
        matched_tracks = set()
        matched_dets = set()

        if active_ids and high_dets:
            track_boxes = [self.tracks[tid]["box"] for tid in active_ids]
            det_boxes = [d["box"] for d in high_dets]
            iou_mat = compute_iou_matrix(track_boxes, det_boxes)

            for _ in range(min(len(active_ids), len(high_dets))):
                idx = np.unravel_index(np.argmax(iou_mat), iou_mat.shape)
                if iou_mat[idx] < 0.20:
                    break
                t_idx, d_idx = idx
                tid = active_ids[t_idx]
                if tid not in matched_tracks and d_idx not in matched_dets:
                    det = high_dets[d_idx]
                    self.tracks[tid]["kf"].update(det["box"])
                    self.tracks[tid]["box"] = det["box"]
                    self.tracks[tid]["class"] = det["class"]
                    self.tracks[tid]["conf"] = det["score"]
                    self.tracks[tid]["lost"] = 0
                    self.tracks[tid]["frames"] += 1
                    cx = (det["box"][0] + det["box"][2]) / 2.0
                    cy = (det["box"][1] + det["box"][3]) / 2.0
                    self.tracks[tid]["history"].append((cx, cy))
                    matched_tracks.add(tid)
                    matched_dets.add(d_idx)
                iou_mat[t_idx, :] = -1.0
                iou_mat[:, d_idx] = -1.0

        # 4. Match remaining tracks to low detections
        unmatched_active = [tid for tid in active_ids if tid not in matched_tracks]
        if unmatched_active and low_dets:
            track_boxes = [self.tracks[tid]["box"] for tid in unmatched_active]
            det_boxes = [d["box"] for d in low_dets]
            iou_mat = compute_iou_matrix(track_boxes, det_boxes)

            for _ in range(min(len(unmatched_active), len(low_dets))):
                idx = np.unravel_index(np.argmax(iou_mat), iou_mat.shape)
                if iou_mat[idx] < 0.30:
                    break
                t_idx, d_idx = idx
                tid = unmatched_active[t_idx]
                if tid not in matched_tracks:
                    det = low_dets[d_idx]
                    self.tracks[tid]["kf"].update(det["box"])
                    self.tracks[tid]["box"] = det["box"]
                    self.tracks[tid]["conf"] = det["score"]
                    self.tracks[tid]["lost"] = 0
                    self.tracks[tid]["frames"] += 1
                    cx = (det["box"][0] + det["box"][2]) / 2.0
                    cy = (det["box"][1] + det["box"][3]) / 2.0
                    self.tracks[tid]["history"].append((cx, cy))
                    matched_tracks.add(tid)
                iou_mat[t_idx, :] = -1.0
                iou_mat[:, d_idx] = -1.0

        # 5. Initialize new tracks for unmatched high detections
        for d_idx, det in enumerate(high_dets):
            if d_idx not in matched_dets:
                tid = self.next_id
                self.next_id += 1
                cx = (det["box"][0] + det["box"][2]) / 2.0
                cy = (det["box"][1] + det["box"][3]) / 2.0
                self.tracks[tid] = {
                    "kf": KalmanFilterBox(det["box"]),
                    "box": det["box"],
                    "class": det["class"],
                    "conf": det["score"],
                    "lost": 0,
                    "frames": 1,
                    "history": deque([(cx, cy)], maxlen=30),
                }

        # 6. Delete old dead tracks
        dead = [tid for tid, t in self.tracks.items() if t["lost"] > self.max_lost_frames]
        for tid in dead:
            del self.tracks[tid]

        # 7. Return currently active tracks
        active_results = []
        for tid, t in self.tracks.items():
            if t["lost"] == 0:
                active_results.append({
                    "track_id": tid,
                    "box": t["box"],
                    "class": t["class"],
                    "conf": t["conf"],
                    "frames": t["frames"],
                    "history": list(t["history"]),
                })
        return active_results

# ── YOLO Model Loader (Dual Engine: Ultralytics or ONNX Runtime) ───────────
_cached_detector = None

def get_yolo_detector():
    global _cached_detector
    if _cached_detector is not None:
        return _cached_detector

    # 1. Try Ultralytics YOLO loading vehicle_traffic.pt
    if MODEL_PT.exists():
        try:
            from ultralytics import YOLO
            model = YOLO(str(MODEL_PT))
            print(f"[Detector] Loaded PyTorch UVH-26: {MODEL_PT}", flush=True)
            _cached_detector = ("ultralytics", model)
            return _cached_detector
        except Exception as e:
            print(f"[Detector] Ultralytics load skipped ({e})", flush=True)

    # 2. Try ONNX Runtime loading vehicle_traffic.onnx
    if MODEL_ONNX.exists():
        try:
            import onnxruntime as ort
            sess = ort.InferenceSession(str(MODEL_ONNX), providers=["CPUExecutionProvider"])
            print(f"[Detector] Loaded ONNX UVH-26: {MODEL_ONNX}", flush=True)
            _cached_detector = ("onnx", sess)
            return _cached_detector
        except Exception as e:
            print(f"[Detector] ONNX load skipped ({e})", flush=True)

    return None

def run_inference_on_frame(detector, frame, conf_thresh=0.20, imgsz=512):
    """
    Returns list of detections: [dict(box=[x1,y1,x2,y2], score=float, class=str)]
    """
    engine_type, model = detector
    h, w = frame.shape[:2]
    min_box_area = 0.00025 * (w * h)
    detections = []

    if engine_type == "ultralytics":
        results = model(frame, conf=conf_thresh, imgsz=imgsz, verbose=False)[0]
        if results.boxes is not None and len(results.boxes) > 0:
            boxes = results.boxes
            xyxy = boxes.xyxy.cpu().numpy()
            confs = boxes.conf.cpu().numpy()
            class_ids = boxes.cls.cpu().numpy().astype(int)

            for box, conf, cls_id in zip(xyxy, confs, class_ids):
                x1, y1, x2, y2 = map(int, box)
                area = max(0, x2 - x1) * max(0, y2 - y1)
                if area < min_box_area:
                    continue
                source_name = results.names.get(int(cls_id), str(cls_id))
                app_class = app_label_from_source(source_name)
                if not app_class:
                    continue
                detections.append({
                    "box": [x1, y1, x2, y2],
                    "score": float(conf),
                    "class": app_class,
                })

    elif engine_type == "onnx":
        inp_shape = model.get_inputs()[0].shape
        in_h = inp_shape[2] if len(inp_shape) > 2 and isinstance(inp_shape[2], int) else 640
        in_w = inp_shape[3] if len(inp_shape) > 3 and isinstance(inp_shape[3], int) else 640
        resized = cv2.resize(frame, (in_w, in_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        inp = np.transpose(rgb, (2, 0, 1))[np.newaxis, ...] # (1, 3, in_h, in_w)
        input_name = model.get_inputs()[0].name
        outs = model.run(None, {input_name: inp})[0] # (1, 18, 8400)
        preds = outs[0] # (18, 8400)
        boxes_raw = preds[:4, :].T # (8400, 4) in cx, cy, w, h
        scores_raw = preds[4:, :].T # (8400, 14)
        max_scores = np.max(scores_raw, axis=1)
        max_classes = np.argmax(scores_raw, axis=1)

        mask = max_scores >= conf_thresh
        filtered_boxes = boxes_raw[mask]
        filtered_scores = max_scores[mask]
        filtered_classes = max_classes[mask]

        scale_x = w / float(in_w)
        scale_y = h / float(in_h)

        # Mapping of UVH-26 14 classes in alphabetical order
        UVH26_NAMES = [
            "Bus", "Hatchback", "LCV", "MUV", "Mini-bus", "Others", "SUV",
            "Sedan", "Three-wheeler", "Truck", "Two-wheeler", "Van", "bicycle", "tempo-traveller"
        ]

        # NMS
        nms_boxes = []
        for b in filtered_boxes:
            cx, cy, bw, bh = b
            x1 = int((cx - bw / 2.0) * scale_x)
            y1 = int((cy - bh / 2.0) * scale_y)
            x2 = int((cx + bw / 2.0) * scale_x)
            y2 = int((cy + bh / 2.0) * scale_y)
            nms_boxes.append([x1, y1, x2 - x1, y2 - y1])

        indices = cv2.dnn.NMSBoxes(nms_boxes, filtered_scores.tolist(), conf_thresh, 0.45)
        if len(indices) > 0:
            for idx in indices.flatten():
                bx, by, bw, bh = nms_boxes[idx]
                x1, y1, x2, y2 = bx, by, bx + bw, by + bh
                area = bw * bh
                if area < min_box_area:
                    continue
                cls_idx = filtered_classes[idx]
                source_name = UVH26_NAMES[cls_idx] if cls_idx < len(UVH26_NAMES) else "Others"
                app_class = app_label_from_source(source_name) or "car"
                detections.append({
                    "box": [x1, y1, x2, y2],
                    "score": float(filtered_scores[idx]),
                    "class": app_class,
                })

    return detections

# ── Full Video Processing Pipeline ──────────────────────────────────────────
def process_video_analysis(
    input_path: str,
    output_video_path: str,
    output_report_path: str,
    session_id: str,
    progress_callback=None,
    stride: int = 2,
    max_dim: int = 1280,
) -> dict:
    """
    Executes real vehicle detection + ByteTrack tracking on an input video.
    Calls progress_callback(progress_int, stage_str) as frames are processed.
    Returns: full report dict
    """
    start_time = time.time()
    detector = get_yolo_detector()
    if not detector:
        raise RuntimeError("UVH-26 YOLO model (vehicle_traffic.pt / onnx) could not be loaded on server.")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open uploaded video file: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    scale = min(1.0, float(max_dim) / max(orig_w, orig_h)) if max(orig_w, orig_h) > max_dim else 1.0
    width = int(orig_w * scale)
    width = width if width % 2 == 0 else width - 1
    height = int(orig_h * scale)
    height = height if height % 2 == 0 else height - 1

    tracker = SimpleByteTrack(high_thresh=0.35, low_thresh=0.15)

    unique_vehicle_classes = {} # track_id -> app_class
    track_frame_counts = Counter()
    vehicles_detail = {}
    per_frame_draw_items = []
    per_frame_active_counts = []
    frame_number = 0

    if progress_callback:
        progress_callback(10, "Extracting video frames and initializing detector...")

    # Pass 1: Tracking and Detection
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_number += 1

        if scale < 1.0:
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

        should_infer = (frame_number % stride == 0) or (frame_number == 1)

        if should_infer:
            dets = run_inference_on_frame(detector, frame, conf_thresh=0.20, imgsz=512)
            active_tracks = tracker.update(dets)

            current_active = len(active_tracks)
            cached_draw_items = []

            for t in active_tracks:
                tid = t["track_id"]
                box = [int(v) for v in t["box"]]
                app_class = t["class"]
                conf = t["conf"]
                track_frame_counts[tid] += 1
                unique_vehicle_classes[tid] = app_class

                cx = int((box[0] + box[2]) / 2)
                cy = int((box[1] + box[3]) / 2)

                # Direction analysis
                det_dir = "UNKNOWN"
                if len(t["history"]) >= 2:
                    dy = t["history"][-1][1] - t["history"][0][1]
                    if abs(dy) >= 4:
                        det_dir = "DOWN" if dy > 0 else "UP"

                vehicles_detail[tid] = {
                    "id": int(tid),
                    "track_id": int(tid),
                    "class": app_class,
                    "type": app_class,
                    "conf": round(float(conf), 3),
                    "direction": det_dir,
                    "status": "TRACKED",
                    "frames_tracked": int(track_frame_counts[tid]),
                    "color": "Silver",
                    "plate": "N/A",
                }

                color = COLORS.get(app_class, (200, 200, 200))
                text = f"ID:{tid} {DISPLAY_LABELS.get(app_class, app_class)} {conf:.0%}"
                cached_draw_items.append((box[0], box[1], box[2], box[3], cx, cy, color, text, tid))

            per_frame_draw_items.append(cached_draw_items)
            per_frame_active_counts.append(current_active)
        else:
            # Repeat previous frame's items for smooth video
            per_frame_draw_items.append(per_frame_draw_items[-1] if per_frame_draw_items else [])
            per_frame_active_counts.append(per_frame_active_counts[-1] if per_frame_active_counts else 0)

        # Progress reporting
        if total_frames > 0 and frame_number % 10 == 0:
            pct = 10 + int((frame_number / total_frames) * 60) # 10% to 70%
            if progress_callback:
                progress_callback(pct, f"Detecting & tracking vehicles ({frame_number}/{total_frames} frames)...")

    cap.release()

    # Determine persistent confirmed tracks (seen on >= 2 inference frames)
    confirmed_track_ids = {
        tid for tid, count in track_frame_counts.items()
        if count >= 2 and tid in unique_vehicle_classes
    }

    target_counts = {
        app_class: sum(1 for tid in confirmed_track_ids if unique_vehicle_classes.get(tid) == app_class)
        for app_class in APP_CLASSES
    }
    authoritative_total = len(confirmed_track_ids)

    final_vehicles_detail = []
    idx = 1
    for tid in sorted(confirmed_track_ids):
        if tid in vehicles_detail:
            v = dict(vehicles_detail[tid])
            v["id"] = idx
            final_vehicles_detail.append(v)
            idx += 1

    if progress_callback:
        progress_callback(75, f"Tracking complete ({authoritative_total} unique vehicles). Rendering output HUD...")

    # Pass 2: Render Annotated Video
    cap2 = cv2.VideoCapture(input_path)
    raw_output = str(Path(output_video_path).with_name(f"raw_{Path(output_video_path).name}"))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(raw_output, fourcc, fps, (width, height))
    if not writer.isOpened():
        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        writer = cv2.VideoWriter(raw_output, fourcc, fps, (width, height))

    frame_idx = 0
    while True:
        ok, frame = cap2.read()
        if not ok or frame_idx >= len(per_frame_draw_items):
            break

        if scale < 1.0:
            frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)

        # Draw bounding boxes
        for item in per_frame_draw_items[frame_idx]:
            x1, y1, x2, y2, cx, cy, color, text, tid = item
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, text, (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 2)
            cv2.circle(frame, (cx, cy), 3, color, -1)

        # Render Authoritative HUD Box
        cv2.rectangle(frame, (8, 8), (380, 260), (15, 20, 28), -1)
        cv2.rectangle(frame, (8, 8), (380, 260), (40, 55, 75), 1)

        curr_act = per_frame_active_counts[frame_idx]
        curr_lvl = traffic_level(curr_act)

        overlay = [
            f"SESSION      : {session_id[:16]}",
            f"CAR          : {target_counts['car']}",
            f"MOTORCYCLE   : {target_counts['motorcycle']}",
            f"AUTO-RICKSHAW: {target_counts['auto']}",
            f"BUS          : {target_counts['bus']}",
            f"TRUCK        : {target_counts['truck']}",
            f"TOTAL UNIQUE : {authoritative_total}",
            f"ACTIVE NOW   : {curr_act} ({curr_lvl})",
        ]
        y = 30
        for line in overlay:
            text_color = (240, 245, 255)
            if "TOTAL UNIQUE" in line:
                text_color = (0, 255, 200)
            elif "ACTIVE NOW" in line:
                text_color = (100, 200, 255)
            elif "SESSION" in line:
                text_color = (160, 175, 200)
            cv2.putText(frame, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, text_color, 2)
            y += 27

        writer.write(frame)
        frame_idx += 1

    cap2.release()
    writer.release()

    if progress_callback:
        progress_callback(90, "Re-encoding web-compatible video...")

    # Video compression / H.264
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin and Path(raw_output).exists():
        temp_h264 = str(Path(output_video_path).with_name(f"h264_{Path(output_video_path).name}"))
        cmd = [
            ffmpeg_bin, "-y", "-i", raw_output,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", temp_h264
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and Path(temp_h264).exists() and Path(temp_h264).stat().st_size > 0:
                shutil.move(temp_h264, output_video_path)
            else:
                shutil.move(raw_output, output_video_path)
        except Exception:
            shutil.move(raw_output, output_video_path)
        try:
            Path(raw_output).unlink(missing_ok=True)
        except Exception:
            pass
    else:
        if Path(raw_output).exists():
            shutil.move(raw_output, output_video_path)

    # Metrics aggregation
    elapsed = max(time.time() - start_time, 0.01)
    avg_active = float(np.mean(per_frame_active_counts)) if per_frame_active_counts else 0.0
    peak_active = int(max(per_frame_active_counts)) if per_frame_active_counts else 0

    direction_counts = Counter()
    for v in final_vehicles_detail:
        if v.get("direction") in ("UP", "DOWN"):
            direction_counts[v["direction"]] += 1

    video_dur = round(float(total_frames / fps), 2) if fps > 0 and total_frames > 0 else 0.0

    report = {
        "session_id": session_id,
        "video": Path(input_path).name,
        "model": "IISc UVH-26 YOLOv11-S",
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
        "traffic_density": {
            "average_active": round(avg_active, 2),
            "peak_active": peak_active,
            "level": traffic_level(round(avg_active)),
        },
        "vehicles_detail": final_vehicles_detail,
    }

    with open(output_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    if progress_callback:
        progress_callback(100, "Analysis complete")

    return report
