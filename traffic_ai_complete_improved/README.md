# AI Intelligent Traffic Monitoring - UVH-26 Ready Package

This package is now configured to use the **IISc UVH-26 YOLOv11-S Indian-traffic model** instead of the small custom 75-image model.

The actual model is bundled in the project root as:

    vehicle_traffic.pt

It is the UVH-26 `UVH-26-MV-YOLOv11-S.pt` checkpoint renamed for compatibility with the application.

## What it does

`main.py` performs:

- Indian-traffic vehicle detection with UVH-26
- normalization to `car`, `motorcycle`, `auto`, `bus`, `truck`
- ByteTrack persistent IDs
- one-time counting when a vehicle crosses the configured line
- up/down direction
- active traffic density and LOW/MEDIUM/HIGH/SEVERE status
- relative speed in pixels/second
- optional real km/h after camera calibration
- annotated output video
- JSON traffic report

`api.py` provides:

- `GET /health`
- `POST /detect`

The API uses the same five-class mapping as the video pipeline.

## Class mapping

UVH-26 has 14 original classes. The application keeps the vehicle categories below:

    Hatchback       -> car
    Sedan           -> car
    SUV             -> car
    MUV             -> car
    Van             -> car
    Bus             -> bus
    Mini-bus        -> bus
    Truck           -> truck
    LCV             -> truck
    Three-wheeler   -> auto
    Two-wheeler     -> motorcycle

`tempo-traveller`, `bicycle`, and `Others` are ignored by the dashboard vehicle pipeline.

See `MODEL_CLASSES.txt` for the exact taxonomy.

## Run traffic processing

Put your input video beside `main.py` and name it:

    video.mp4

Then:

    pip install -r requirements.txt
    python main.py

Outputs:

    traffic_output.mp4
    traffic_report.json

### Camera settings

This package is tuned to the high-angle vertical camera used during testing:

    DENSITY_TOP_RATIO = 0.35
    DENSITY_BOTTOM_RATIO = 0.80

For another camera, these should be adjusted.

### Speed

Without calibration, speed is reported as pixels/second. Do not present it as km/h.

To enable physical speed, configure `METERS_PER_PIXEL` after calibrating the camera. A homography/perspective calibration is preferred for production.

## Run the API

    uvicorn api:app --host 0.0.0.0 --port 8000

Health:

    GET http://localhost:8000/health

Image detection:

    POST http://localhost:8000/detect

The response contains normalized five-class detections, bounding boxes, confidence, and source UVH-26 class.

## Next.js integration

Your existing premium dark dashboard can consume the `/detect` JSON without changing its visual design. The backend can later be extended with a video-processing job endpoint if the dashboard needs to upload recorded video directly.

Recommended dashboard cards:

    Total Vehicles
    Cars
    Motorcycles
    Auto-rickshaws
    Buses
    Trucks
    Traffic Level
    Up / Down
    Average Speed

## Training note

You **do not need to train a model to use this package**. The bundled UVH-26 model is already trained for Indian urban traffic.

Your earlier 75-image Roboflow model can be kept as a separate experimental checkpoint, but it is not the default model here.

If later you want to fine-tune on your own CCTV footage, create a larger, carefully reviewed dataset from the same camera view. Do not mix class-ID orders between the 14-class UVH-26 model and the five-class application dataset.

## Safety / project scope

Speed and traffic violations are estimates unless the camera is calibrated and the relevant event logic is explicitly implemented. A model detection alone is not proof of a legal violation.
