"""FastAPI service for the UVH-26 Indian traffic model.

POST /detect accepts one image and returns detections normalized to the
five dashboard classes: car, motorcycle, auto, bus, truck.
"""
from pathlib import Path
from collections import Counter

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from ultralytics import YOLO

SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_PATH = SCRIPT_DIR / "vehicle_traffic.pt"
CONFIDENCE = 0.25
IMG_SIZE = 640
MIN_BOX_AREA_RATIO = 0.00025

UVH26_TO_APP = {
    "Hatchback": "car", "Sedan": "car", "SUV": "car", "MUV": "car",
    "Bus": "bus", "Truck": "truck", "Three-wheeler": "auto",
    "Two-wheeler": "motorcycle", "LCV": "truck", "Mini-bus": "bus",
    "Van": "car", "bicycle": "motorcycle",
    "tempo-traveller": "bus", "Others": "car",
}

app = FastAPI(title="AI Intelligent Traffic Monitoring API", version="2.0")

if not Path(MODEL_PATH).exists():
    raise RuntimeError(f"{MODEL_PATH} not found")
model = YOLO(MODEL_PATH)


def normalize_source(label):
    clean = str(label).strip().lower().replace("_", " ")
    aliases = {
        "three wheeler": "Three-wheeler", "three-wheeler": "Three-wheeler",
        "auto": "Three-wheeler", "autorickshaw": "Three-wheeler", "auto rickshaw": "Three-wheeler",
        "auto-rickshaw": "Three-wheeler",
        "two wheeler": "Two-wheeler", "two-wheeler": "Two-wheeler",
        "motorcycle": "Two-wheeler", "motorbike": "Two-wheeler", "bike": "Two-wheeler",
        "mini bus": "Mini-bus", "mini-bus": "Mini-bus",
        "tempo traveller": "tempo-traveller", "tempo-traveller": "tempo-traveller",
        "bicycle": "bicycle", "others": "Others", "other": "Others",
    }
    if clean in aliases:
        return aliases[clean]
    for candidate in UVH26_TO_APP:
        if clean == candidate.lower():
            return candidate
    return str(label)


def app_label(source):
    return UVH26_TO_APP.get(normalize_source(source))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_PATH,
        "model_source": "IISc UVH-26 YOLOv11-S",
        "classes": ["car", "motorcycle", "auto", "bus", "truck"],
    }


@app.post("/detect")
async def detect(
    file: UploadFile = File(...),
    augment: bool = Query(False, description="Use test-time augmentation (slower)."),
):
    data = await file.read()
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    frame_area = float(image.shape[0] * image.shape[1])
    min_box_area = MIN_BOX_AREA_RATIO * frame_area

    result = model.predict(
        source=image,
        conf=CONFIDENCE,
        imgsz=IMG_SIZE,
        augment=augment,
        verbose=False,
    )[0]

    detections = []
    counter = Counter()
    source_counter = Counter()

    if result.boxes is not None:
        for box, confidence, class_id in zip(
            result.boxes.xyxy.cpu().numpy(),
            result.boxes.conf.cpu().numpy(),
            result.boxes.cls.cpu().numpy().astype(int),
        ):
            x1, y1, x2, y2 = map(float, box)
            box_area = max(0.0, x2 - x1) * max(0.0, y2 - y1)
            if box_area < min_box_area:
                continue

            source_name = result.names[int(class_id)]
            label = app_label(source_name)
            if label is None:
                continue

            counter[label] += 1
            source_counter[source_name] += 1
            detections.append({
                "class": label,
                "source_class": source_name,
                "confidence": round(float(confidence), 4),
                "box": {
                    "x1": round(x1, 2), "y1": round(y1, 2),
                    "x2": round(x2, 2), "y2": round(y2, 2),
                },
            })

    return {
        "model": MODEL_PATH,
        "model_source": "IISc UVH-26 YOLOv11-S",
        "counts": {c: int(counter[c]) for c in ["car", "motorcycle", "auto", "bus", "truck"]},
        "total": len(detections),
        "detections": detections,
        "source_class_counts": dict(source_counter),
        "augment": augment,
    }
