"""
SURVILLENCE TRAFFIC — Vercel Serverless Function Entrypoint
===========================================================
Re-exports the unified Flask `app` from root `app.py`.
This guarantees identical behavior across local `python app.py`
and Vercel online deployment at https://ai-smart-traffic-detector.vercel.app.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import unified Flask app
from app import app, get_yolo_detector, process_video_analysis

# Export for WSGI server
__all__ = ["app"]
