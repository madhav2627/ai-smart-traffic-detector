"""Optional future trainer for a separate five-class custom model.

IMPORTANT: the bundled vehicle_traffic.pt is the 14-class UVH-26 model
with inference-time mapping. Do not overwrite it by blindly training a
5-class dataset with this script. Keep any experimental custom checkpoint
under a different filename until validated.
"""
from pathlib import Path
import shutil
from ultralytics import YOLO

BASE_MODEL = "yolo11s.pt"
DATA = "dataset/data.yaml"
FINAL_MODEL_NAME = "vehicle_traffic_custom.pt"
EPOCHS = 120
IMAGE_SIZE = 800
BATCH = 16
PATIENCE = 25
WORKERS = 4

if not Path(DATA).exists():
    raise FileNotFoundError(f"{DATA} not found")

model = YOLO(BASE_MODEL)
model.train(
    data=DATA, epochs=EPOCHS, imgsz=IMAGE_SIZE, batch=BATCH,
    patience=PATIENCE, workers=WORKERS, pretrained=True,
    project="runs/traffic", name="vehicle_traffic_custom", exist_ok=True,
    optimizer="AdamW", lr0=0.001, cos_lr=True,
    label_smoothing=0.05, weight_decay=0.0005,
    multi_scale=True, hsv_h=0.015, hsv_s=0.7, hsv_v=0.4,
    degrees=5.0, translate=0.10, scale=0.5, shear=2.0,
    perspective=0.0, flipud=0.0, fliplr=0.5,
    mosaic=1.0, mixup=0.10, copy_paste=0.0, close_mosaic=10,
)

best_path = Path("runs/traffic/vehicle_traffic_custom/weights/best.pt")
if best_path.exists():
    shutil.copy2(best_path, FINAL_MODEL_NAME)
    print(f"Saved experimental custom model to {FINAL_MODEL_NAME}")
else:
    print("Training finished but best.pt was not found at the expected path.")
