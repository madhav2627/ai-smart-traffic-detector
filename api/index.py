"""
SURVILLENCE TRAFFIC — Online Serverless API
==========================================
Main Vercel Serverless Function entry point.
Exposes Flask `app` for Vercel Python Runtime.

Strictly isolated per-user data store, asynchronous job tracking,
UVH-26 YOLOv11-S + ByteTrack execution, and permanent metadata history.
"""

import os
import sys
import json
import time
import uuid
import queue
import shutil
import threading
from pathlib import Path

from flask import Flask, request, jsonify, Response, send_file, abort
from flask_cors import CORS

# Add root and api directory to sys.path
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import db
from detector import process_video_analysis, MODEL_PT, MODEL_ONNX

# ── Paths & Configuration ───────────────────────────────────────────────────
# In Vercel serverless environment, /tmp is writable.
TMP_DIR = Path("/tmp") if Path("/tmp").exists() else (ROOT_DIR / "storage")
UPLOAD_DIR = TMP_DIR / "traffic_uploads"
RESULTS_DIR = TMP_DIR / "traffic_results"
REPORTS_DIR = TMP_DIR / "traffic_reports"

for d in [UPLOAD_DIR, RESULTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}

app = Flask(__name__)
CORS(app, origins=["*"])

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-User-Id"
    response.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, DELETE, OPTIONS"
    return response

# In-memory progress tracking for active requests
_active_threads: dict[str, threading.Thread] = {}
_threads_lock = threading.Lock()

def get_current_user_id() -> str | None:
    raw = (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or request.form.get("user_id")
    )
    if not raw:
        return None
    cleaned = "".join(c for c in str(raw).strip() if c.isalnum() or c in ("_", "-"))
    return cleaned if cleaned else None

def safe_filename(name: str) -> str:
    name = Path(name).name
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
    return "".join(c if c in keep else "_" for c in name)[:100]

# ── Health Route ────────────────────────────────────────────────────────────
@app.route("/health")
@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "mode": "Vercel Online Serverless",
        "model_pt_exists": MODEL_PT.exists(),
        "model_onnx_exists": MODEL_ONNX.exists(),
        "detector": "IISc UVH-26 YOLOv11-S + ByteTrack",
        "database": "Persistent Isolated Storage",
        "max_physical_videos_per_user": 1,
    })

# ── Authentication Endpoints ────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
@app.route("/api/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    name = data.get("fullName") or data.get("name")
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    user, error, code = db.create_user(name, username, email, password)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "user": user}), code

@app.route("/api/auth/login", methods=["POST"])
@app.route("/api/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    identifier = data.get("identifier") or data.get("username") or data.get("email")
    password = data.get("password")

    user, error, code = db.authenticate_user(identifier, password)
    if error:
        return jsonify({"ok": False, "error": error, "code": "USER_NOT_FOUND" if code == 404 else "INVALID_PASSWORD"}), code
    return jsonify({"ok": True, "user": user}), code

@app.route("/api/auth/me", methods=["GET"])
@app.route("/api/me", methods=["GET"])
def auth_me():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"authenticated": False, "error": "Not authenticated"}), 401
    user = db.get_user(user_id)
    if not user:
        return jsonify({"authenticated": False, "error": "User does not exist"}), 401
    return jsonify({"authenticated": True, "user": user})

@app.route("/api/auth/settings", methods=["POST"])
def auth_settings():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if db.update_user_settings(user_id, data):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "User not found"}), 404

@app.route("/api/auth/profile", methods=["POST"])
def auth_profile():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    user, error, code = db.update_user_profile(user_id, data.get("fullName"), data.get("email"))
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "user": user})

# ── Video Analysis & Asynchronous Processing ────────────────────────────────
def _run_detection_worker(user_id: str, job_id: str, session_id: str, input_path: str, output_path: str, report_path: str, orig_name: str):
    try:
        def on_progress(pct, stage):
            db.update_job_progress(job_id, pct, stage)

        report = process_video_analysis(
            input_path=input_path,
            output_video_path=output_path,
            output_report_path=report_path,
            session_id=session_id,
            progress_callback=on_progress,
            stride=2,
            max_dim=1280
        )

        # Save to database
        analysis_data = {
            "sessionId": session_id,
            "filename": orig_name,
            "status": "completed",
            "total_vehicles": report.get("total_vehicles", 0),
            "cars": report.get("cars", 0),
            "motorcycles": report.get("motorcycles", 0),
            "auto_rickshaws": report.get("auto_rickshaws", 0),
            "autos": report.get("auto_rickshaws", 0),
            "buses": report.get("buses", 0),
            "trucks": report.get("trucks", 0),
            "video_duration": report.get("video_duration", 0),
            "processing_time": report.get("processing_time_seconds", 0),
            "input_video": input_path,
            "output_video": output_path,
            "report_path": report_path,
        }
        db.add_analysis(user_id, analysis_data)
        db.save_report(user_id, session_id, report)
        db.complete_job(job_id, status="completed")

        # Clean up older physical video files for this user (Max 1 physical video retained)
        entries = db.get_user_history(user_id)
        for e in entries:
            sid = e.get("sessionId")
            if sid != session_id:
                for k in ("input_video", "output_video"):
                    p = e.get(k)
                    if p and Path(p).exists() and str(p) != output_path and str(p) != input_path:
                        try:
                            Path(p).unlink()
                        except Exception:
                            pass

    except Exception as exc:
        print(f"[Detector Worker Error] {exc}", flush=True)
        db.complete_job(job_id, status="failed", error=str(exc))
        # Add failed analysis to history for record
        db.add_analysis(user_id, {
            "sessionId": session_id,
            "filename": orig_name,
            "status": "failed",
            "total_vehicles": 0,
            "input_video": input_path,
            "output_video": "",
            "report_path": "",
        })
    finally:
        with _threads_lock:
            _active_threads.pop(job_id, None)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized: user_id is required"}), 401

    # Enforce 1 active job per user
    existing_job = db.get_active_job(user_id)
    if existing_job:
        return jsonify({
            "error": "An analysis is already in progress. Please wait for it to complete.",
            "code": "ALREADY_PROCESSING",
            "activeJob": existing_job,
        }), 409

    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    f = request.files["video"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported format '{ext}'. Allowed: MP4, AVI, MOV, MKV, WebM"}), 400

    session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    orig_name = safe_filename(f.filename)

    input_path = str(UPLOAD_DIR / f"{session_id}_{orig_name}")
    output_path = str(RESULTS_DIR / f"{session_id}_output.mp4")
    report_path = str(REPORTS_DIR / f"{session_id}_report.json")

    try:
        f.save(input_path)
    except Exception as exc:
        return jsonify({"error": f"Failed to save video: {exc}"}), 500

    if not Path(input_path).exists() or Path(input_path).stat().st_size == 0:
        return jsonify({"error": "Uploaded video file is empty or missing"}), 400

    # Create server-side processing job
    job = db.create_job(user_id, session_id, orig_name)

    # Launch processing in server-side worker
    t = threading.Thread(
        target=_run_detection_worker,
        args=(user_id, job["jobId"], session_id, input_path, output_path, report_path, orig_name),
        daemon=True,
    )
    with _threads_lock:
        _active_threads[job["jobId"]] = t
    t.start()

    return jsonify({
        "sessionId": session_id,
        "session_id": session_id,
        "jobId": job["jobId"],
        "status": "processing",
        "filename": orig_name,
        "stage": "Upload received and validated",
        "userId": user_id,
    })

@app.route("/api/active-job")
def active_job():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"job": None})
    job = db.get_active_job(user_id)
    return jsonify({"job": job, "active": bool(job)})

@app.route("/api/completed-job")
def completed_job():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"job": None})
    job = db.get_recently_completed_job(user_id)
    return jsonify({"job": job})

@app.route("/api/completed-job/<session_id>/dismiss", methods=["POST"])
def dismiss_completed_job(session_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False}), 401
    db.dismiss_completed_job(user_id, session_id)
    return jsonify({"ok": True})

@app.route("/api/job/<job_id>")
def get_job_status(job_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    job = db.get_active_job(user_id)
    if job and job.get("jobId") == job_id:
        return jsonify(job)
    # Check completed
    recent = db.get_recently_completed_job(user_id)
    if recent and recent.get("jobId") == job_id:
        return jsonify(recent)
    return jsonify({"status": "unknown"})

@app.route("/api/result/<session_id>")
def result(session_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    analysis = db.get_user_analysis(user_id, session_id)
    if not analysis:
        return jsonify({"error": "Analysis not found or access denied"}), 404

    report_data = db.get_report(user_id, session_id)
    if not report_data and analysis.get("report_path"):
        rp = Path(analysis["report_path"])
        if rp.exists():
            try:
                report_data = json.loads(rp.read_text("utf-8"))
            except Exception:
                pass

    return jsonify({
        "status": analysis["status"],
        "report": report_data,
        "sessionId": session_id,
        "userId": user_id,
        "videoAvailable": analysis.get("videoAvailable", False),
        "historyEntry": analysis,
    })

@app.route("/api/video/<session_id>")
def video(session_id: str):
    user_id = get_current_user_id()
    if not user_id:
        abort(401)

    analysis = db.get_user_analysis(user_id, session_id)
    if not analysis:
        abort(404)

    out_path = analysis.get("output_video")
    if out_path and Path(out_path).exists():
        return send_file(str(out_path), mimetype="video/mp4", conditional=True)

    # Check RESULTS_DIR directly
    candidates = list(RESULTS_DIR.glob(f"{session_id}*.*"))
    if candidates:
        return send_file(str(candidates[0]), mimetype="video/mp4", conditional=True)

    abort(404)

@app.route("/api/history")
def history():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify([])
    entries = db.get_user_history(user_id)
    return jsonify(entries)

@app.route("/api/history/<session_id>", methods=["DELETE"])
def delete_history(session_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    ok = db.delete_user_analysis(user_id, session_id)
    if not ok:
        return jsonify({"error": "Not found or access denied"}), 404
    return jsonify({"status": "deleted", "sessionId": session_id})

@app.route("/api/storage/stats")
def storage_stats():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({
            "videos_in_bytes": 0,
            "videos_out_bytes": 0,
            "reports_bytes": 0,
            "total_bytes": 0,
            "history_count": 0,
            "retained_videos": 0,
        })
    entries = db.get_user_history(user_id)
    retained = sum(1 for e in entries if e.get("videoAvailable", False))

    in_size = sum(Path(e["input_video"]).stat().st_size for e in entries if e.get("input_video") and Path(e["input_video"]).exists())
    out_size = sum(Path(e["output_video"]).stat().st_size for e in entries if e.get("output_video") and Path(e["output_video"]).exists())
    rep_size = sum(Path(e["report_path"]).stat().st_size for e in entries if e.get("report_path") and Path(e["report_path"]).exists())

    return jsonify({
        "videos_in_bytes": in_size,
        "videos_out_bytes": out_size,
        "reports_bytes": rep_size,
        "total_bytes": in_size + out_size + rep_size,
        "history_count": len(entries),
        "retained_videos": retained,
    })

@app.route("/api/storage/cleanup", methods=["POST"])
def storage_cleanup():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"removed_files": 0})
    entries = db.get_user_history(user_id)
    retained_outputs = {e.get("output_video") for e in entries if e.get("videoAvailable", False)}
    removed = 0

    for e in entries:
        if not e.get("videoAvailable", False):
            for k in ("input_video", "output_video"):
                p = e.get(k)
                if p and p not in retained_outputs and Path(p).exists():
                    try:
                        Path(p).unlink()
                        removed += 1
                    except Exception:
                        pass
    return jsonify({"removed_files": removed})

# ── CCTV & Camera Connectivity ──────────────────────────────────────────────
@app.route("/api/cameras", methods=["GET"])
def cameras_list():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify([]), 200
    cameras = db.get_cameras(user_id)
    return jsonify(cameras)

@app.route("/api/cameras", methods=["POST"])
def cameras_create():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    name = data.get("name") or data.get("cameraName")
    camera_type = data.get("type") or data.get("cameraType") or "IP Camera"
    stream_url = data.get("streamUrl") or data.get("url") or ""
    username = data.get("username")
    password = data.get("password")
    port = data.get("port")

    cam, error, code = db.create_camera(user_id, name, camera_type, stream_url, username, password, port)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "camera": cam}), code

@app.route("/api/cameras/<camera_id>", methods=["GET"])
def cameras_get(camera_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    cam = db.get_camera(user_id, camera_id)
    if not cam:
        return jsonify({"error": "Camera not found or access denied"}), 404
    return jsonify(cam)

@app.route("/api/cameras/<camera_id>", methods=["PUT", "POST"])
def cameras_update(camera_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    cam, error, code = db.update_camera(user_id, camera_id, data)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "camera": cam})

@app.route("/api/cameras/<camera_id>", methods=["DELETE"])
def cameras_delete(camera_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    ok = db.delete_camera(user_id, camera_id)
    if not ok:
        return jsonify({"ok": False, "error": "Camera not found or unauthorized"}), 404
    return jsonify({"ok": True, "deleted": camera_id})

def _probe_camera_connection(stream_url: str):
    """
    Genuine check of stream reachability.
    Detects private local area network IPs (unreachable from cloud).
    """
    stream_url = (stream_url or "").strip()
    if not stream_url:
        return "NOT CONFIGURED", None, None, "No stream URL provided."

    # Check for private LAN / localhost IP addresses
    private_prefixes = ("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
                        "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.",
                        "172.28.", "172.29.", "172.30.", "172.31.", "127.", "localhost")
    for prefix in private_prefixes:
        if prefix in stream_url:
            return (
                "PRIVATE LAN / UNREACHABLE",
                None,
                None,
                f"Camera URL contains '{prefix}', which is on a private local network. "
                "Cloud-deployed servers cannot reach private LAN cameras unless routed through a public secure endpoint."
            )

    if not (stream_url.startswith("rtsp://") or stream_url.startswith("http://") or stream_url.startswith("https://")):
        return "UNSUPPORTED STREAM", None, None, "Stream URL must begin with rtsp://, http://, or https://"

    # Attempt short reachability probe with OpenCV
    try:
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            return "OFFLINE", None, None, "Camera stream could not be opened from cloud."
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None:
            h, w = frame.shape[:2]
            return "ONLINE", f"{w} × {h}", 25.0, None
        return "NO SIGNAL", None, None, "Stream opened but no frames received."
    except Exception as exc:
        return "CONNECTION ERROR", None, None, str(exc)

@app.route("/api/cameras/test", methods=["POST"])
def cameras_test_raw():
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    stream_url = data.get("streamUrl") or data.get("url") or ""
    status, resolution, fps, error = _probe_camera_connection(stream_url)
    return jsonify({
        "status": status,
        "online": status == "ONLINE",
        "resolution": resolution,
        "fps": fps,
        "error": error,
    })

@app.route("/api/cameras/<camera_id>/test", methods=["POST"])
def cameras_test_saved(camera_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    cam = db.get_camera(user_id, camera_id, include_password=True)
    if not cam:
        return jsonify({"ok": False, "error": "Camera not found or access denied"}), 404

    status, resolution, fps, error = _probe_camera_connection(cam.get("streamUrl"))
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    updates = {"status": status}
    if status == "ONLINE":
        updates["lastConnected"] = now_iso
        if resolution:
            updates["resolution"] = resolution
        if fps:
            updates["fps"] = fps

    updated_cam, _, _ = db.update_camera(user_id, camera_id, updates)
    return jsonify({
        "status": status,
        "online": status == "ONLINE",
        "resolution": resolution,
        "fps": fps,
        "error": error,
        "camera": updated_cam,
    })

@app.route("/api/cameras/<camera_id>/stats")
def camera_live_stats(camera_id: str):
    user_id = get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    cam = db.get_camera(user_id, camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    return jsonify({
        "cameraId": camera_id,
        "cameraName": cam["name"],
        "cameraType": cam["type"],
        "stats": {
            "active_vehicles": 0,
            "cars": 0,
            "motorcycles": 0,
            "autos": 0,
            "buses": 0,
            "trucks": 0,
            "fps": cam.get("fps") or 25.0,
            "status": cam.get("status", "NOT CONFIGURED"),
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
