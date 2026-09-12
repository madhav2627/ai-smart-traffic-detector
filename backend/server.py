"""
SURVILLENCE TRAFFIC — Local Backend Bridge
==========================================
Flask server bridging the browser frontend and
traffic_ai_complete_improved/main.py vehicle detector.

Per-User Isolated Storage:
  storage/users/<user_id>/
    uploads/        ← uploaded input videos (max 1 physical at a time)
    results/        ← processed annotated videos (max 1 physical at a time)
    reports/        ← JSON detection reports (kept forever)
    history.json    ← permanent analysis history (kept forever, unlimited entries)

History is PERMANENT. Physical video storage is limited to 1 per user.
When a new video is successfully processed, the previous physical video files
are removed but the previous history entry remains with videoAvailable=false.

Routes:
  GET    /health                      — server + detector status
  POST   /api/analyze                 — upload video, start detection subprocess
  GET    /api/active-job              — get active processing job for current user
  GET    /api/completed-job           — get most recent completed job (last 2h) for current user
  GET    /api/progress/<session>      — SSE stream of detection progress (owner only)
  GET    /api/result/<session>        — fetch JSON report for a session (owner only)
  GET    /api/video/<session>         — stream processed video for playback (owner only)
  GET    /api/history                 — get analysis history for current user only
  DELETE /api/history/<session>       — delete a history entry for current user only
  GET    /api/storage/stats           — storage usage stats for current user only
  POST   /api/storage/cleanup         — delete unreferenced upload files for current user only

NO external APIs. NO cloud. All local.
"""

import cv2
import hashlib
import json
import numpy as np
import os
import queue
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, abort
from flask_cors import CORS

# ── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR  = Path(__file__).resolve().parent.parent          # project root
DETECTOR  = BASE_DIR / "traffic_ai_complete_improved" / "main.py"
MODEL     = BASE_DIR / "traffic_ai_complete_improved" / "vehicle_traffic.pt"
STORAGE   = BASE_DIR / "storage"
USERS_DIR = STORAGE / "users"
USERS_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH   = STORAGE / "users.db"

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
MAX_UPLOAD_MB = 2048  # 2 GB

# Max 1 physical video retained per user at a time.
# History entries are UNLIMITED and PERMANENT — this only governs physical file storage.
MAX_PHYSICAL_VIDEOS_PER_USER = 1

# How long (seconds) to remember a completed job for the "completion notification"
COMPLETED_JOB_TTL = 7200  # 2 hours

app = Flask(__name__)
CORS(app, origins=["*"])

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-User-Id"
    response.headers["Access-Control-Allow-Methods"] = "GET, PUT, POST, DELETE, OPTIONS"
    return response

# In-memory registry: session_id → {userId, status, progress_queue, report, proc, ...}
_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()
_db_lock = threading.Lock()

# Live camera stats cache: cam_id -> {active, cars, motorcycles, autos, buses, trucks, fps, last_seen}
_live_camera_stats: dict[str, dict] = {}
_live_camera_lock = threading.Lock()
_live_yolo_model = None

# ── Persistent User Database (SQLite) ────────────────────────────────────────

def _get_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _db_lock:
        conn = _get_db()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    email TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    role TEXT DEFAULT 'operator',
                    settings TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    camera_type TEXT NOT NULL,
                    stream_url TEXT NOT NULL,
                    username TEXT,
                    password TEXT,
                    port INTEGER,
                    status TEXT DEFAULT 'NOT CONFIGURED',
                    last_connected TEXT,
                    resolution TEXT,
                    fps REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.commit()
        finally:
            conn.close()

_init_db()


def _db_hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _db_create_user(name: str, username: str, email: str, password: str):
    name = (name or "").strip()
    username = (username or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not name:
        return None, "Full name is required.", 400
    if not email or "@" not in email:
        return None, "A valid email address is required.", 400
    if not username or len(username) < 3:
        return None, "Username must be at least 3 characters.", 400
    if not all(c.isalnum() or c in ("_", "-") for c in username):
        return None, "Username can only contain letters, numbers, hyphens, and underscores.", 400
    if len(password) < 6:
        return None, "Password must be at least 6 characters.", 400

    salt = uuid.uuid4().hex[:16]
    pw_hash = _db_hash_password(password, salt)
    user_id = f"usr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if row:
                return None, "Username is already taken.", 409
            row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if row:
                return None, "An account with this email already exists.", 409

            conn.execute(
                """
                INSERT INTO users (id, name, username, email, password_hash, salt, created_at, role, settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'operator', '{}')
                """,
                (user_id, name, username, email, pw_hash, salt, now_iso)
            )
            conn.commit()
        finally:
            conn.close()

    # Initialize user's dedicated storage directory
    _user_dir(user_id)
    hf = _user_history_file(user_id)
    if not hf.exists():
        hf.write_text("[]", encoding="utf-8")

    return {
        "id": user_id,
        "userId": user_id,
        "fullName": name,
        "name": name,
        "username": username,
        "email": email,
        "role": "operator",
        "createdAt": now_iso,
        "settings": {},
    }, None, 201


def _db_authenticate_user(identifier: str, password: str):
    identifier = (identifier or "").strip()
    password = password or ""
    if not identifier:
        return None, "Email or username is required.", 400
    if not password:
        return None, "Password is required.", 400

    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identifier, identifier)
            ).fetchone()
        finally:
            conn.close()

    if not row:
        return None, "Account not found", 404

    computed_hash = _db_hash_password(password, row["salt"])
    if computed_hash != row["password_hash"]:
        return None, "Incorrect password", 401

    try:
        settings = json.loads(row["settings"] or "{}")
    except Exception:
        settings = {}

    return {
        "id": row["id"],
        "userId": row["id"],
        "fullName": row["name"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "createdAt": row["created_at"],
        "settings": settings,
    }, None, 200


def _db_get_user(user_id: str):
    uid = _clean_user_id(user_id)
    if not uid:
        return None
    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    try:
        settings = json.loads(row["settings"] or "{}")
    except Exception:
        settings = {}
    return {
        "id": row["id"],
        "userId": row["id"],
        "fullName": row["name"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "role": row["role"],
        "createdAt": row["created_at"],
        "settings": settings,
    }


def _db_update_settings(user_id: str, new_settings: dict):
    uid = _clean_user_id(user_id)
    if not uid:
        return False
    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute("SELECT settings FROM users WHERE id = ?", (uid,)).fetchone()
            if not row:
                return False
            try:
                curr = json.loads(row["settings"] or "{}")
            except Exception:
                curr = {}
            curr.update(new_settings)
            conn.execute("UPDATE users SET settings = ? WHERE id = ?", (json.dumps(curr), uid))
            conn.commit()
            return True
        finally:
            conn.close()


def _db_update_profile(user_id: str, full_name: str | None, email: str | None):
    uid = _clean_user_id(user_id)
    if not uid:
        return None, "Invalid user ID", 400
    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
            if not row:
                return None, "User not found", 404
            new_name = full_name.strip() if full_name else row["name"]
            new_email = email.strip().lower() if email else row["email"]
            if new_email != row["email"]:
                conflict = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, uid)).fetchone()
                if conflict:
                    return None, "Email is already in use by another account.", 409
            conn.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (new_name, new_email, uid))
            conn.commit()
            return {
                "id": uid,
                "userId": uid,
                "fullName": new_name,
                "name": new_name,
                "username": row["username"],
                "email": new_email,
                "role": row["role"],
            }, None, 200
        finally:
            conn.close()


# ── Camera Database Helpers (Strict User Isolation) ──────────────────────────

def _db_get_cameras(user_id: str) -> list:
    uid = _clean_user_id(user_id)
    if not uid:
        return []
    with _db_lock:
        conn = _get_db()
        try:
            rows = conn.execute(
                "SELECT * FROM cameras WHERE user_id = ? ORDER BY created_at DESC",
                (uid,)
            ).fetchall()
            result = []
            for r in rows:
                result.append({
                    "cameraId": r["id"],
                    "id": r["id"],
                    "userId": r["user_id"],
                    "name": r["name"],
                    "type": r["camera_type"],
                    "streamUrl": r["stream_url"],
                    "username": r["username"] or "",
                    "hasPassword": bool(r["password"]),
                    "port": r["port"],
                    "status": r["status"] or "NOT CONFIGURED",
                    "lastConnected": r["last_connected"],
                    "resolution": r["resolution"],
                    "fps": r["fps"],
                    "createdAt": r["created_at"],
                })
            return result
        finally:
            conn.close()


def _db_get_camera(user_id: str, camera_id: str, include_password: bool = False) -> dict | None:
    uid = _clean_user_id(user_id)
    if not uid or not camera_id:
        return None
    with _db_lock:
        conn = _get_db()
        try:
            r = conn.execute(
                "SELECT * FROM cameras WHERE id = ? AND user_id = ?",
                (camera_id, uid)
            ).fetchone()
            if not r:
                return None
            res = {
                "cameraId": r["id"],
                "id": r["id"],
                "userId": r["user_id"],
                "name": r["name"],
                "type": r["camera_type"],
                "streamUrl": r["stream_url"],
                "username": r["username"] or "",
                "hasPassword": bool(r["password"]),
                "port": r["port"],
                "status": r["status"] or "NOT CONFIGURED",
                "lastConnected": r["last_connected"],
                "resolution": r["resolution"],
                "fps": r["fps"],
                "createdAt": r["created_at"],
            }
            if include_password:
                res["password"] = r["password"] or ""
            return res
        finally:
            conn.close()


def _db_create_camera(user_id: str, name: str, camera_type: str, stream_url: str,
                       username: str = None, password: str = None, port: int = None):
    uid = _clean_user_id(user_id)
    if not uid:
        return None, "Unauthorized: user_id is required", 401

    name = (name or "").strip()
    if not name:
        return None, "Camera name is required.", 400

    camera_type = (camera_type or "IP Camera").strip()
    stream_url = (stream_url or "").strip()
    if not stream_url and camera_type not in ("Webcam", "Local Camera"):
        return None, "Stream or connection URL is required.", 400

    cam_id = f"cam_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _db_lock:
        conn = _get_db()
        try:
            conn.execute(
                """
                INSERT INTO cameras (id, user_id, name, camera_type, stream_url, username, password, port, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NOT CONFIGURED', ?)
                """,
                (cam_id, uid, name, camera_type, stream_url, username or "", password or "", int(port) if port else None, now_iso)
            )
            conn.commit()
        finally:
            conn.close()

    return _db_get_camera(uid, cam_id), None, 201


def _db_update_camera(user_id: str, camera_id: str, data: dict):
    uid = _clean_user_id(user_id)
    if not uid or not camera_id:
        return None, "Invalid request", 400

    with _db_lock:
        conn = _get_db()
        try:
            row = conn.execute("SELECT * FROM cameras WHERE id = ? AND user_id = ?", (camera_id, uid)).fetchone()
            if not row:
                return None, "Camera not found or access denied", 404

            name = data.get("name") if data.get("name") is not None else row["name"]
            camera_type = data.get("type") if data.get("type") is not None else row["camera_type"]
            stream_url = data.get("streamUrl") if data.get("streamUrl") is not None else row["stream_url"]
            username = data.get("username") if data.get("username") is not None else row["username"]
            # Only update password if explicitly provided non-empty
            pw_val = data.get("password")
            password = pw_val if (pw_val is not None and pw_val != "") else row["password"]
            port = data.get("port") if data.get("port") is not None else row["port"]
            status = data.get("status") if data.get("status") is not None else row["status"]
            last_connected = data.get("lastConnected") if data.get("lastConnected") is not None else row["last_connected"]
            resolution = data.get("resolution") if data.get("resolution") is not None else row["resolution"]
            fps = data.get("fps") if data.get("fps") is not None else row["fps"]

            conn.execute(
                """
                UPDATE cameras SET name = ?, camera_type = ?, stream_url = ?, username = ?, password = ?, port = ?,
                                   status = ?, last_connected = ?, resolution = ?, fps = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, camera_type, stream_url, username, password, port, status, last_connected, resolution, fps, camera_id, uid)
            )
            conn.commit()
        finally:
            conn.close()

    return _db_get_camera(uid, camera_id), None, 200


def _db_delete_camera(user_id: str, camera_id: str) -> bool:
    uid = _clean_user_id(user_id)
    if not uid or not camera_id:
        return False
    with _db_lock:
        conn = _get_db()
        try:
            cur = conn.execute("DELETE FROM cameras WHERE id = ? AND user_id = ?", (camera_id, uid))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def _test_camera_connection(stream_url: str, camera_type: str, username: str = None, password: str = None, port: int = None):
    """
    Real probe of camera reachability using OpenCV with timeout.
    Returns: (status, resolution_str, fps_val, error_msg)
    """
    stream_url = (stream_url or "").strip()
    camera_type = (camera_type or "IP Camera").strip()

    target = stream_url

    # Check if local camera/webcam index
    if camera_type in ("Webcam", "Local Camera") or stream_url.isdigit():
        try:
            target = int(stream_url) if stream_url.isdigit() else 0
        except Exception:
            target = 0
    elif camera_type in ("RTSP", "IP Camera"):
        if not (stream_url.startswith("rtsp://") or stream_url.startswith("http://") or stream_url.startswith("https://")):
            return "UNSUPPORTED STREAM", None, None, "Invalid stream URL. Must begin with rtsp:// or http://"
        if username and password and "@" not in stream_url and stream_url.startswith("rtsp://"):
            target = stream_url.replace("rtsp://", f"rtsp://{username}:{password}@", 1)
    else:
        # Unsupported stream protocol
        if not stream_url.startswith(("rtsp://", "http://", "https://")) and not Path(stream_url).exists():
            return "UNSUPPORTED STREAM", None, None, "Stream type configured but not currently supported."

    result = {"status": "CONNECTION ERROR", "resolution": None, "fps": None, "error": "Connection attempt timed out"}

    def probe():
        cap = None
        try:
            if isinstance(target, str) and target.startswith("rtsp://"):
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;3000000"

            cap = cv2.VideoCapture(target)
            if not cap.isOpened():
                result["status"] = "OFFLINE"
                result["error"] = "Camera stream could not be opened. Verify IP, port, or credentials."
                return

            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                result["status"] = "NO SIGNAL"
                result["error"] = "Stream reachable but no video frames received."
                return

            h, w = frame.shape[:2]
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            if fps <= 0 or fps > 240:
                fps = 25.0

            result["status"] = "ONLINE"
            result["resolution"] = f"{w} × {h}"
            result["fps"] = round(float(fps), 1)
            result["error"] = None
        except Exception as exc:
            result["status"] = "CONNECTION ERROR"
            result["error"] = str(exc)
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    t = threading.Thread(target=probe, daemon=True)
    t.start()
    t.join(timeout=3.5)

    if t.is_alive():
        return "TIMEOUT", None, None, "Connection attempt timed out after 3.5s."

    return result["status"], result["resolution"], result["fps"], result["error"]


def _get_live_detector():
    """Lazily load UVH-26 YOLO model for real live detection."""
    global _live_yolo_model
    if _live_yolo_model is None:
        if MODEL.exists():
            try:
                from ultralytics import YOLO
                _live_yolo_model = YOLO(str(MODEL))
            except Exception as exc:
                print(f"[Detector] Live YOLO load error: {exc}", flush=True)
                _live_yolo_model = False
        else:
            _live_yolo_model = False
    return _live_yolo_model if _live_yolo_model is not False else None


# ── User Storage Helpers ─────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """Sanitize an uploaded filename."""
    name = Path(name).name
    keep = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- ")
    return "".join(c if c in keep else "_" for c in name)[:120]


def _clean_user_id(uid: str | None) -> str | None:
    """Sanitize user_id to prevent directory traversal."""
    if not uid:
        return None
    cleaned = "".join(c for c in str(uid).strip() if c.isalnum() or c in ("_", "-"))
    return cleaned if cleaned else None


def _get_current_user_id() -> str | None:
    """Extract authenticated userId from headers, query parameters, or form data."""
    raw = (
        request.headers.get("X-User-Id")
        or request.args.get("user_id")
        or request.form.get("user_id")
    )
    return _clean_user_id(raw)


def _user_dir(user_id: str) -> Path:
    """Return the dedicated storage directory for this user, creating subfolders if needed."""
    uid = _clean_user_id(user_id)
    if not uid:
        raise ValueError("Invalid or missing user_id")
    p = USERS_DIR / uid
    for sub in ["uploads", "results", "reports"]:
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


def _user_history_file(user_id: str) -> Path:
    return _user_dir(user_id) / "history.json"


def _user_history_load(user_id: str) -> list:
    try:
        hf = _user_history_file(user_id)
        if hf.exists():
            data = json.loads(hf.read_text("utf-8-sig"))
            if isinstance(data, list):
                return [e for e in data if isinstance(e, dict)]
            elif isinstance(data, dict):
                return [data]
    except Exception:
        pass
    return []


def _user_history_save(user_id: str, entries: list):
    hf = _user_history_file(user_id)
    hf.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _user_history_add(user_id: str, entry: dict):
    """Add a session to user's permanent history (no FIFO cap on records)."""
    entries = _user_history_load(user_id)
    sid = entry.get("sessionId") or entry.get("session_id")
    # Deduplicate: remove any existing entry for this session
    entries = [e for e in entries if (e.get("sessionId") != sid and e.get("session_id") != sid)]
    entries.insert(0, entry)
    _user_history_save(user_id, entries)


def _user_history_update_video_available(user_id: str, session_id: str, available: bool):
    """Mark a history entry's videoAvailable flag without deleting the record."""
    entries = _user_history_load(user_id)
    changed = False
    for e in entries:
        if e.get("sessionId") == session_id or e.get("session_id") == session_id:
            e["videoAvailable"] = available
            changed = True
    if changed:
        _user_history_save(user_id, entries)


def _user_history_delete(user_id: str, session_id: str) -> bool:
    """Delete a history entry (user explicitly removes it). Physical files are also cleaned."""
    entries = _user_history_load(user_id)
    target = next(
        (e for e in entries if (e.get("sessionId") == session_id or e.get("session_id") == session_id)),
        None
    )
    if not target:
        return False

    # Remove physical files if they still exist
    for k in ("input_video", "output_video", "report_path"):
        path_str = target.get(k)
        if path_str:
            p = Path(path_str)
            if not p.is_absolute():
                p = BASE_DIR / p
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    new_entries = [
        e for e in entries
        if (e.get("sessionId") != session_id and e.get("session_id") != session_id)
    ]
    _user_history_save(user_id, new_entries)
    return True


def _delete_session_physical_files(entry: dict):
    """Delete the physical video files for a history entry, leaving the record intact."""
    for k in ("input_video", "output_video"):
        path_str = entry.get(k)
        if path_str:
            p = Path(path_str)
            if not p.is_absolute():
                p = BASE_DIR / p
            if p.exists():
                try:
                    p.unlink()
                    print(f"[Storage] Deleted physical file: {p}", flush=True)
                except Exception as exc:
                    print(f"[Storage] Could not delete {p}: {exc}", flush=True)


def _enforce_physical_video_limit(user_id: str, new_session_id: str):
    """
    After a new video is successfully processed, enforce the 1-physical-video-per-user policy.
    Deletes physical video files for ALL sessions except the new one,
    and marks those old sessions as videoAvailable=false in history.
    """
    entries = _user_history_load(user_id)
    changed = False
    for e in entries:
        sid = e.get("sessionId") or e.get("session_id")
        if sid == new_session_id:
            continue
        # Only touch entries that still think they have a video
        if e.get("videoAvailable", True):
            _delete_session_physical_files(e)
            e["videoAvailable"] = False
            changed = True
    if changed:
        _user_history_save(user_id, entries)


def _user_has_active_session(user_id: str) -> bool:
    """Return True if this user already has a processing session in memory."""
    with _sessions_lock:
        for sess in _sessions.values():
            if sess.get("userId") == user_id and sess.get("status") == "processing":
                return True
    return False


def _get_active_session(user_id: str) -> dict | None:
    with _sessions_lock:
        for sid, sess in _sessions.items():
            if sess.get("userId") == user_id and sess.get("status") == "processing":
                return {"sessionId": sid, **sess}
    return None


def _get_recently_completed_session(user_id: str) -> dict | None:
    """Return the most recently completed session for this user within COMPLETED_JOB_TTL."""
    now = time.time()
    with _sessions_lock:
        candidates = [
            (sid, sess) for sid, sess in _sessions.items()
            if sess.get("userId") == user_id
            and sess.get("status") == "completed"
            and (now - sess.get("completed_at", 0)) < COMPLETED_JOB_TTL
            and not sess.get("notification_dismissed", False)
        ]
    if not candidates:
        return None
    # Most recently completed
    candidates.sort(key=lambda x: x[1].get("completed_at", 0), reverse=True)
    sid, sess = candidates[0]
    return {"sessionId": sid, "filename": sess.get("original_filename"), "completedAt": sess.get("completed_at")}


# ── Detector Runner ──────────────────────────────────────────────────────────

def _run_detector(user_id: str, session_id: str, input_video: str, output_video: str, report_path: str):
    """Run main.py as a subprocess; push progress lines to the session queue."""
    with _sessions_lock:
        sess = _sessions.get(session_id)
    if not sess:
        return

    q: queue.Queue = sess["progress_queue"]

    def _push(msg: str):
        q.put(msg)

    _push("data: Detection engine starting...\n\n")

    cmd = [
        sys.executable,
        str(DETECTOR),
        "--input",  input_video,
        "--output", output_video,
        "--report", report_path,
        "--session-id", session_id,
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with _sessions_lock:
            _sessions[session_id]["proc"] = proc

        for line in proc.stdout:
            line = line.rstrip()
            if line:
                _push(f"data: {line}\n\n")

        proc.wait()
        rc = proc.returncode

        if rc == 0 and Path(report_path).exists():
            try:
                report_data = json.loads(Path(report_path).read_text("utf-8"))
            except Exception:
                report_data = {}

            with _sessions_lock:
                _sessions[session_id]["status"] = "completed"
                _sessions[session_id]["report"] = report_data
                _sessions[session_id]["completed_at"] = time.time()

            # Persist to user's permanent history
            history_entry = {
                "sessionId":       session_id,
                "session_id":      session_id,
                "userId":          user_id,
                "user_id":         user_id,
                "filename":        sess.get("original_filename", "video.mp4"),
                "date":            time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status":          "completed",
                "total_vehicles":  report_data.get("total_vehicles", 0),
                "cars":            report_data.get("cars", 0),
                "motorcycles":     report_data.get("motorcycles", 0),
                "auto_rickshaws":  report_data.get("auto_rickshaws", 0),
                "buses":           report_data.get("buses", 0),
                "trucks":          report_data.get("trucks", 0),
                "video_duration":  report_data.get("video_duration", 0),
                "processing_time": report_data.get("processing_time_seconds", 0),
                "input_video":     input_video,
                "output_video":    output_video,
                "report_path":     report_path,
                "videoAvailable":  True,
            }
            _user_history_add(user_id, history_entry)

            # Enforce 1-physical-video-per-user: delete previous retained video files
            _enforce_physical_video_limit(user_id, session_id)

            _push("data: [TrafficAI] Analysis completed successfully.\n\n")
        else:
            with _sessions_lock:
                _sessions[session_id]["status"] = "failed"
            # Save a failed entry so history is accurate
            _user_history_add(user_id, {
                "sessionId":      session_id,
                "session_id":     session_id,
                "userId":         user_id,
                "user_id":        user_id,
                "filename":       sess.get("original_filename", "video.mp4"),
                "date":           time.strftime("%Y-%m-%dT%H:%M:%S"),
                "status":         "failed",
                "total_vehicles": 0,
                "videoAvailable": False,
            })
            _push("data: [TrafficAI] Analysis failed. Check your video file.\n\n")

    except Exception as exc:
        with _sessions_lock:
            if session_id in _sessions:
                _sessions[session_id]["status"] = "failed"
        _push(f"data: [TrafficAI] Error: {exc}\n\n")
    finally:
        _push("data: __DONE__\n\n")


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({
        "status":           "ok",
        "detector":         str(DETECTOR),
        "detector_exists":  DETECTOR.exists(),
        "model_exists":     MODEL.exists(),
        "storage":          str(STORAGE),
        "architecture":     "isolated_per_user_permanent_history",
        "user_db_exists":   DB_PATH.exists(),
        "max_physical_videos_per_user": MAX_PHYSICAL_VIDEOS_PER_USER,
    })


# ── Authentication Endpoints ──────────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
@app.route("/api/register", methods=["POST"])
def auth_register():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    name = data.get("fullName") or data.get("name")
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    user, error, code = _db_create_user(name, username, email, password)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "user": user}), code


@app.route("/api/auth/login", methods=["POST"])
@app.route("/api/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    identifier = data.get("identifier") or data.get("username") or data.get("email")
    password = data.get("password")

    user, error, code = _db_authenticate_user(identifier, password)
    if error:
        return jsonify({"ok": False, "error": error, "code": "USER_NOT_FOUND" if code == 404 else "INVALID_PASSWORD"}), code
    return jsonify({"ok": True, "user": user}), code


@app.route("/api/auth/me", methods=["GET"])
@app.route("/api/me", methods=["GET"])
def auth_me():
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"authenticated": False, "error": "Not authenticated"}), 401
    user = _db_get_user(user_id)
    if not user:
        return jsonify({"authenticated": False, "error": "User does not exist"}), 401
    return jsonify({"authenticated": True, "user": user})


@app.route("/api/auth/settings", methods=["POST"])
def auth_settings():
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    if _db_update_settings(user_id, data):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "User not found"}), 404


@app.route("/api/auth/profile", methods=["POST"])
def auth_profile():
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    user, error, code = _db_update_profile(user_id, data.get("fullName"), data.get("email"))
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "user": user})


@app.route("/api/analyze", methods=["POST"])
def analyze():
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized: user_id is required"}), 401

    # Enforce 1 active job per user
    if _user_has_active_session(user_id):
        return jsonify({
            "error": "An analysis is already in progress. Please wait for it to complete before starting a new one.",
            "code":  "ALREADY_PROCESSING",
        }), 409

    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    f = request.files["video"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type: {ext}. Supported: MP4, AVI, MOV, MKV, WebM"}), 400

    # User's dedicated private directories
    user_p     = _user_dir(user_id)
    session_id = f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    safe_name  = _safe_filename(f.filename)

    input_path  = str(user_p / "uploads"  / f"{session_id}_{safe_name}")
    output_path = str(user_p / "results"  / f"{session_id}_output.mp4")
    report_path = str(user_p / "reports"  / f"{session_id}_report.json")

    try:
        f.save(input_path)
    except Exception as exc:
        return jsonify({"error": f"Upload failed: {exc}"}), 500

    # Verify the file was saved correctly before registering the session
    if not Path(input_path).exists() or Path(input_path).stat().st_size == 0:
        return jsonify({"error": "Upload validation failed: file is empty or missing"}), 500

    with _sessions_lock:
        _sessions[session_id] = {
            "sessionId":         session_id,
            "session_id":        session_id,
            "userId":            user_id,
            "user_id":           user_id,
            "status":            "processing",
            "progress_queue":    queue.Queue(),
            "report":            None,
            "proc":              None,
            "original_filename": safe_name,
            "started_at":        time.time(),
            "completed_at":      None,
            "notification_dismissed": False,
        }

    t = threading.Thread(
        target=_run_detector,
        args=(user_id, session_id, input_path, output_path, report_path),
        daemon=True,
    )
    t.start()

    return jsonify({
        "session_id": session_id,
        "sessionId":  session_id,
        "status":     "processing",
        "userId":     user_id,
        "filename":   safe_name,
    })


@app.route("/api/active-job")
def active_job():
    """Return the active in-progress job for the requesting user only."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"job": None})

    with _sessions_lock:
        for sid, sess in _sessions.items():
            if sess.get("userId") == user_id and sess.get("status") == "processing":
                return jsonify({
                    "job": {
                        "sessionId":  sid,
                        "session_id": sid,
                        "filename":   sess.get("original_filename"),
                        "status":     "processing",
                        "startedAt":  sess.get("started_at"),
                    }
                })
    return jsonify({"job": None})


@app.route("/api/completed-job")
def completed_job():
    """Return the most recently completed job (within TTL) for the requesting user.
    Used by the global processing monitor to show completion notifications.
    """
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"job": None})

    job = _get_recently_completed_session(user_id)
    return jsonify({"job": job})


@app.route("/api/completed-job/<session_id>/dismiss", methods=["POST"])
def dismiss_completed_job(session_id: str):
    """Mark a completed job's notification as dismissed so it won't show again."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False}), 401

    with _sessions_lock:
        sess = _sessions.get(session_id)
        if sess and sess.get("userId") == user_id:
            sess["notification_dismissed"] = True

    return jsonify({"ok": True})


@app.route("/api/progress/<session_id>")
def progress(session_id: str):
    """Server-Sent Events stream of detector stdout (strictly user-protected)."""
    user_id = _get_current_user_id()
    with _sessions_lock:
        sess = _sessions.get(session_id)
    if not sess:
        return jsonify({"error": "Unknown session"}), 404

    # Strict ownership check: User B cannot listen to User A's progress
    if user_id and sess.get("userId") and sess.get("userId") != user_id:
        return jsonify({"error": "Forbidden: Access denied"}), 403

    def generate():
        q: queue.Queue = sess["progress_queue"]
        # If already completed, send done immediately
        if sess.get("status") in ("completed", "failed"):
            yield f"data: [TrafficAI] Session already {sess.get('status')}.\n\n"
            yield "data: __DONE__\n\n"
            return
        while True:
            try:
                msg = q.get(timeout=60)
                yield msg
                if "__DONE__" in msg:
                    break
            except queue.Empty:
                yield "data: [TrafficAI] Still processing...\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/result/<session_id>")
def result(session_id: str):
    """Fetch report JSON for a session (strictly user-protected)."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    with _sessions_lock:
        sess = _sessions.get(session_id)

    if sess:
        if sess.get("userId") != user_id:
            return jsonify({"error": "Forbidden: Access denied"}), 403
        return jsonify({
            "status":    sess["status"],
            "report":    sess.get("report"),
            "sessionId": session_id,
            "userId":    user_id,
        })

    # Search strictly in the requesting user's private history
    entries = _user_history_load(user_id)
    entry = next(
        (e for e in entries if (e.get("sessionId") == session_id or e.get("session_id") == session_id)),
        None,
    )
    if not entry:
        return jsonify({"error": "Session not found"}), 404

    report_path = Path(entry.get("report_path", ""))
    if not report_path.is_absolute():
        report_path = BASE_DIR / report_path
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text("utf-8-sig"))
            return jsonify({
                "status":         "completed",
                "report":         data,
                "sessionId":      session_id,
                "userId":         user_id,
                "videoAvailable": entry.get("videoAvailable", False),
            })
        except Exception:
            pass

    # Report file missing but history entry exists — return metadata
    return jsonify({
        "status":         entry.get("status", "unknown"),
        "report":         None,
        "sessionId":      session_id,
        "userId":         user_id,
        "videoAvailable": entry.get("videoAvailable", False),
        "historyEntry":   entry,
    })


@app.route("/api/video/<session_id>")
def video(session_id: str):
    """Stream processed video for playback (strictly user-protected)."""
    user_id = _get_current_user_id()
    if not user_id:
        abort(401)

    # Search strictly in the requesting user's results folder
    user_p = _user_dir(user_id)
    candidates = list((user_p / "results").glob(f"{session_id}_output.*"))

    if not candidates:
        # Fall back to path stored in history entry
        entries = _user_history_load(user_id)
        entry = next(
            (e for e in entries if (e.get("sessionId") == session_id or e.get("session_id") == session_id)),
            None,
        )
        if entry:
            p = Path(entry.get("output_video", ""))
            if not p.is_absolute():
                p = BASE_DIR / p
            if p.exists():
                candidates = [p]

    if not candidates:
        abort(404)

    return send_file(str(candidates[0]), mimetype="video/mp4", conditional=True)


@app.route("/api/history")
def history():
    """Return full permanent analysis history for current user only."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify([])

    entries = _user_history_load(user_id)

    # Reconcile videoAvailable flag against actual filesystem
    changed = False
    for e in entries:
        if isinstance(e, dict) and e.get("videoAvailable", False):
            out_path = Path(e.get("output_video", ""))
            if not out_path.is_absolute():
                out_path = BASE_DIR / out_path
            if not out_path.exists():
                e["videoAvailable"] = False
                changed = True

    if changed:
        _user_history_save(user_id, entries)

    return jsonify(entries)


@app.route("/api/history/<session_id>", methods=["DELETE"])
def delete_history(session_id: str):
    """Delete a history entry and its physical files for the current user only."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    ok = _user_history_delete(user_id, session_id)
    if not ok:
        return jsonify({"error": "Not found or access denied"}), 404

    with _sessions_lock:
        if session_id in _sessions and _sessions[session_id].get("userId") == user_id:
            _sessions.pop(session_id, None)

    return jsonify({"status": "deleted", "sessionId": session_id})


@app.route("/api/storage/stats")
def storage_stats():
    """Return storage stats for the current user only."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({
            "videos_in_bytes":  0,
            "videos_out_bytes": 0,
            "reports_bytes":    0,
            "total_bytes":      0,
            "history_count":    0,
            "retained_videos":  0,
        })

    user_p = _user_dir(user_id)

    def _dir_size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0

    entries = _user_history_load(user_id)
    retained = sum(1 for e in entries if e.get("videoAvailable", False))

    return jsonify({
        "videos_in_bytes":  _dir_size(user_p / "uploads"),
        "videos_out_bytes": _dir_size(user_p / "results"),
        "reports_bytes":    _dir_size(user_p / "reports"),
        "total_bytes":      _dir_size(user_p),
        "history_count":    len(entries),
        "retained_videos":  retained,
    })


@app.route("/api/storage/cleanup", methods=["POST"])
def storage_cleanup():
    """Remove input videos that are no longer referenced in user's history."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"removed_files": 0})

    user_p = _user_dir(user_id)
    entries = _user_history_load(user_id)
    referenced_inputs = {e.get("input_video") for e in entries if e.get("input_video")}
    referenced_outputs = {e.get("output_video") for e in entries if e.get("output_video")}
    removed = 0

    for folder, referenced in [
        (user_p / "uploads", referenced_inputs),
        (user_p / "results", referenced_outputs),
    ]:
        if folder.exists():
            for f in folder.iterdir():
                if f.is_file() and str(f) not in referenced:
                    try:
                        f.unlink()
                        removed += 1
                    except Exception:
                        pass

    return jsonify({"removed_files": removed})


# ── CCTV Connectivity & Camera Management Endpoints ─────────────────────────

@app.route("/api/cameras", methods=["GET"])
def cameras_list():
    """List all configured cameras for the current user (credentials masked)."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify([]), 200
    cameras = _db_get_cameras(user_id)
    return jsonify(cameras)


@app.route("/api/cameras", methods=["POST"])
def cameras_create():
    """Add a new camera for the current user."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    name = data.get("name") or data.get("cameraName")
    camera_type = data.get("type") or data.get("cameraType") or "IP Camera"
    stream_url = data.get("streamUrl") or data.get("url") or ""
    username = data.get("username")
    password = data.get("password")
    port = data.get("port")

    cam, error, code = _db_create_camera(user_id, name, camera_type, stream_url, username, password, port)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "camera": cam}), code


@app.route("/api/cameras/<camera_id>", methods=["GET"])
def cameras_get(camera_id: str):
    """Fetch camera details for owner."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    cam = _db_get_camera(user_id, camera_id)
    if not cam:
        return jsonify({"error": "Camera not found or access denied"}), 404
    return jsonify(cam)


@app.route("/api/cameras/<camera_id>", methods=["PUT", "POST"])
def cameras_update(camera_id: str):
    """Update camera configuration for owner."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    cam, error, code = _db_update_camera(user_id, camera_id, data)
    if error:
        return jsonify({"ok": False, "error": error}), code
    return jsonify({"ok": True, "camera": cam})


@app.route("/api/cameras/<camera_id>", methods=["DELETE"])
def cameras_delete(camera_id: str):
    """Delete camera configuration, verifying camera.user_id == current_user_id."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    ok = _db_delete_camera(user_id, camera_id)
    if not ok:
        return jsonify({"ok": False, "error": "Camera not found or unauthorized"}), 404
    return jsonify({"ok": True, "deleted": camera_id})


@app.route("/api/cameras/test", methods=["POST"])
def cameras_test_raw():
    """Test connection reachability for unsaved camera config."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    stream_url = data.get("streamUrl") or data.get("url") or ""
    camera_type = data.get("type") or data.get("cameraType") or "IP Camera"
    username = data.get("username")
    password = data.get("password")
    port = data.get("port")

    status, resolution, fps, error = _test_camera_connection(stream_url, camera_type, username, password, port)
    return jsonify({
        "status": status,
        "online": status == "ONLINE",
        "resolution": resolution,
        "fps": fps,
        "error": error,
    })


@app.route("/api/cameras/<camera_id>/test", methods=["POST"])
def cameras_test_saved(camera_id: str):
    """Test connection reachability for a saved camera and update its status."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": "Unauthorized"}), 401

    cam = _db_get_camera(user_id, camera_id, include_password=True)
    if not cam:
        return jsonify({"ok": False, "error": "Camera not found or access denied"}), 404

    status, resolution, fps, error = _test_camera_connection(
        cam.get("streamUrl"),
        cam.get("type"),
        cam.get("username"),
        cam.get("password"),
        cam.get("port")
    )

    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    updates = {"status": status}
    if status == "ONLINE":
        updates["lastConnected"] = now_iso
        if resolution:
            updates["resolution"] = resolution
        if fps:
            updates["fps"] = fps

    updated_cam, _, _ = _db_update_camera(user_id, camera_id, updates)

    return jsonify({
        "status": status,
        "online": status == "ONLINE",
        "resolution": resolution,
        "fps": fps,
        "error": error,
        "camera": updated_cam,
    })


@app.route("/api/cameras/<camera_id>/stats", methods=["GET"])
def camera_live_stats(camera_id: str):
    """Fetch real-time vehicle counts for a streaming camera."""
    user_id = _get_current_user_id()
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cam = _db_get_camera(user_id, camera_id)
    if not cam:
        return jsonify({"error": "Camera not found"}), 404

    with _live_camera_lock:
        stats = _live_camera_stats.get(camera_id, {
            "active_vehicles": 0,
            "cars": 0,
            "motorcycles": 0,
            "autos": 0,
            "buses": 0,
            "trucks": 0,
            "fps": cam.get("fps") or 25.0,
            "status": cam.get("status", "NOT CONFIGURED"),
        })

    return jsonify({
        "cameraId": camera_id,
        "cameraName": cam["name"],
        "cameraType": cam["type"],
        "stats": stats
    })


@app.route("/api/cameras/<camera_id>/stream")
def camera_stream(camera_id: str):
    """Live stream (MJPEG) with real-time UVH-26 vehicle detection for authorized user."""
    user_id = _get_current_user_id()
    if not user_id:
        user_id = _clean_user_id(request.args.get("user_id"))
    if not user_id:
        abort(401)

    cam = _db_get_camera(user_id, camera_id, include_password=True)
    if not cam:
        abort(404)

    target = cam["streamUrl"]
    camera_type = cam.get("type", "IP Camera")
    username = cam.get("username", "")
    password = cam.get("password", "")

    if camera_type in ("Webcam", "Local Camera") or (isinstance(target, str) and target.isdigit()):
        try:
            target = int(target) if str(target).isdigit() else 0
        except Exception:
            target = 0
    elif camera_type in ("RTSP", "IP Camera"):
        if username and password and "@" not in target and target.startswith("rtsp://"):
            target = target.replace("rtsp://", f"rtsp://{username}:{password}@", 1)

    def generate_frames():
        if isinstance(target, str) and target.startswith("rtsp://"):
            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;3000000"

        cap = cv2.VideoCapture(target)
        if not cap.isOpened():
            slate = np.zeros((360, 640, 3), dtype=np.uint8)
            cv2.putText(slate, "CAMERA OFFLINE / NO SIGNAL", (100, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 240), 2)
            cv2.putText(slate, f"{cam['name']} - Check stream connection", (120, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
            _, encoded = cv2.imencode(".jpg", slate)
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + encoded.tobytes() + b"\r\n")
            return

        detector = _get_live_detector()
        frame_idx = 0
        last_boxes = []

        class_colors = {
            "car": (250, 200, 0),
            "motorcycle": (153, 211, 52),
            "auto": (60, 146, 251),
            "bus": (250, 139, 167),
            "truck": (182, 114, 244),
        }

        with _live_camera_lock:
            _live_camera_stats[camera_id] = {
                "active_vehicles": 0,
                "cars": 0,
                "motorcycles": 0,
                "autos": 0,
                "buses": 0,
                "trucks": 0,
                "fps": 25.0,
                "status": "ONLINE",
                "timestamp": time.time(),
            }

        try:
            while True:
                ret, frame = cap.read()
                if not ret or frame is None:
                    break
                frame_idx += 1

                h, w = frame.shape[:2]
                if w > 1280:
                    scale = 1280.0 / w
                    frame = cv2.resize(frame, (1280, int(h * scale)))
                    h, w = frame.shape[:2]

                if detector and (frame_idx % 2 == 1 or not last_boxes):
                    try:
                        results = detector(frame, conf=0.20, verbose=False)
                        counts = {"car": 0, "motorcycle": 0, "auto": 0, "bus": 0, "truck": 0}
                        current_boxes = []

                        if results and len(results) > 0 and results[0].boxes is not None:
                            boxes = results[0].boxes
                            for b in boxes:
                                cls_id = int(b.cls[0].item())
                                conf = float(b.conf[0].item())
                                cls_name = results[0].names.get(cls_id, "")
                                sys_path = str(BASE_DIR / "traffic_ai_complete_improved")
                                if sys_path not in sys.path:
                                    sys.path.insert(0, sys_path)
                                from main import app_label_from_source
                                app_cls = app_label_from_source(cls_name) or "car"
                                xyxy = b.xyxy[0].cpu().numpy().astype(int)
                                current_boxes.append((xyxy, app_cls, conf))
                                counts[app_cls] = counts.get(app_cls, 0) + 1

                        last_boxes = current_boxes

                        with _live_camera_lock:
                            _live_camera_stats[camera_id] = {
                                "active_vehicles": len(last_boxes),
                                "cars": counts.get("car", 0),
                                "motorcycles": counts.get("motorcycle", 0),
                                "autos": counts.get("auto", 0),
                                "buses": counts.get("bus", 0),
                                "trucks": counts.get("truck", 0),
                                "fps": round(float(cap.get(cv2.CAP_PROP_FPS) or 25.0), 1),
                                "status": "ONLINE",
                                "timestamp": time.time(),
                            }
                    except Exception:
                        pass

                # Draw detections
                for xyxy, app_cls, conf in last_boxes:
                    x1, y1, x2, y2 = xyxy
                    color = class_colors.get(app_cls, (255, 255, 255))
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label_str = f"{app_cls.upper()} {int(conf * 100)}%"
                    cv2.putText(frame, label_str, (x1, max(20, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                # Draw LIVE indicator
                cv2.circle(frame, (25, 25), 6, (0, 0, 255), -1)
                cv2.putText(frame, f"LIVE - {cam['name']}", (40, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                _, jpeg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
                time.sleep(0.03)
        finally:
            cap.release()
            with _live_camera_lock:
                if camera_id in _live_camera_stats:
                    _live_camera_stats[camera_id]["status"] = "OFFLINE"

    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ── Static frontend serving ───────────────────────────────────────────────────
FRONTEND_DIR = BASE_DIR / "frontend"

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_frontend(path):
    target = FRONTEND_DIR / path
    if target.exists() and target.is_file():
        return send_file(str(target))
    with_html = FRONTEND_DIR / (path + ".html")
    if with_html.exists():
        return send_file(str(with_html))
    return send_file(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    print("=" * 62)
    print("  SURVILLENCE TRAFFIC — Local Server")
    print("  Architecture: Isolated Per-User + Permanent History")
    print(f"  Detector : {DETECTOR}")
    print(f"  Model    : {MODEL} ({'OK' if MODEL.exists() else 'NOT FOUND'})")
    print(f"  Storage  : {STORAGE}")
    print(f"  Users Dir: {USERS_DIR}")
    print("  Opening  : http://localhost:5000")
    print("  LAN      : http://<your-ip>:5000")
    print("=" * 62)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
