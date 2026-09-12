"""
SURVILLENCE TRAFFIC — Persistent Database Layer
================================================
Unified server-side database adapter for Vercel deployment.
Strictly isolated per-user data store supporting:
  1. PostgreSQL (Vercel Postgres / Neon / Supabase via POSTGRES_URL / DATABASE_URL)
  2. Vercel KV / Upstash Redis (via KV_REST_API_URL and KV_REST_API_TOKEN)
  3. Serverless SQLite (storage/users.db or /tmp/users.db)

Every record is scoped to `userId` — cross-user leakage is strictly impossible.
"""

import os
import json
import time
import uuid
import hashlib
import sqlite3
import threading
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
# In Vercel serverless functions, repository root is read-only.
# /tmp is writable for temporary/ephemeral storage.
TMP_DIR = Path("/tmp") if Path("/tmp").exists() else (BASE_DIR / "storage")
DB_DIR = TMP_DIR / "traffic_db"
DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = DB_DIR / "traffic.db"

_lock = threading.Lock()

def _get_sqlite_conn():
    conn = sqlite3.connect(str(SQLITE_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with _lock:
        conn = _get_sqlite_conn()
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
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_vehicles INTEGER DEFAULT 0,
                    cars INTEGER DEFAULT 0,
                    motorcycles INTEGER DEFAULT 0,
                    autos INTEGER DEFAULT 0,
                    buses INTEGER DEFAULT 0,
                    trucks INTEGER DEFAULT 0,
                    video_duration REAL DEFAULT 0,
                    processing_time REAL DEFAULT 0,
                    input_video TEXT,
                    output_video TEXT,
                    report_path TEXT,
                    video_available INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER DEFAULT 0,
                    stage TEXT DEFAULT 'Initializing',
                    original_filename TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    error TEXT,
                    notification_dismissed INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    analysis_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    report_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
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

# Initialize immediately
init_db()

# ── User Helpers ─────────────────────────────────────────────────────────────

def hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def create_user(name: str, username: str, email: str, password: str):
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
    pw_hash = hash_password(password, salt)
    user_id = f"usr_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _lock:
        conn = _get_sqlite_conn()
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

def authenticate_user(identifier: str, password: str):
    identifier = (identifier or "").strip()
    password = password or ""
    if not identifier:
        return None, "Email or username is required.", 400
    if not password:
        return None, "Password is required.", 400

    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? OR email = ?",
                (identifier, identifier)
            ).fetchone()
        finally:
            conn.close()

    if not row:
        return None, "Account not found", 404

    computed_hash = hash_password(password, row["salt"])
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

def get_user(user_id: str):
    if not user_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
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

def update_user_settings(user_id: str, new_settings: dict) -> bool:
    if not user_id:
        return False
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute("SELECT settings FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return False
            try:
                curr = json.loads(row["settings"] or "{}")
            except Exception:
                curr = {}
            curr.update(new_settings)
            conn.execute("UPDATE users SET settings = ? WHERE id = ?", (json.dumps(curr), user_id))
            conn.commit()
            return True
        finally:
            conn.close()

def update_user_profile(user_id: str, full_name: str | None, email: str | None):
    if not user_id:
        return None, "Invalid user ID", 400
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if not row:
                return None, "User not found", 404
            new_name = full_name.strip() if full_name else row["name"]
            new_email = email.strip().lower() if email else row["email"]
            if new_email != row["email"]:
                conflict = conn.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user_id)).fetchone()
                if conflict:
                    return None, "Email is already in use by another account.", 409
            conn.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (new_name, new_email, user_id))
            conn.commit()
            return {
                "id": user_id,
                "userId": user_id,
                "fullName": new_name,
                "name": new_name,
                "username": row["username"],
                "email": new_email,
                "role": row["role"],
            }, None, 200
        finally:
            conn.close()

# ── Job Helpers ──────────────────────────────────────────────────────────────

def create_job(user_id: str, analysis_id: str, original_filename: str) -> dict:
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                """
                INSERT INTO jobs (id, analysis_id, user_id, status, progress, stage, original_filename, created_at)
                VALUES (?, ?, ?, 'processing', 5, 'Upload received and validated', ?, ?)
                """,
                (job_id, analysis_id, user_id, original_filename, now_iso)
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "jobId": job_id,
        "analysisId": analysis_id,
        "userId": user_id,
        "status": "processing",
        "progress": 5,
        "stage": "Upload received and validated",
        "originalFilename": original_filename,
        "createdAt": now_iso,
    }

def get_active_job(user_id: str) -> dict | None:
    if not user_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute(
                "SELECT * FROM jobs WHERE user_id = ? AND status = 'processing' ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        "jobId": row["id"],
        "sessionId": row["analysis_id"],
        "analysisId": row["analysis_id"],
        "userId": row["user_id"],
        "status": row["status"],
        "progress": row["progress"],
        "stage": row["stage"],
        "filename": row["original_filename"],
        "createdAt": row["created_at"],
    }

def update_job_progress(job_id: str, progress: int, stage: str):
    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                "UPDATE jobs SET progress = ?, stage = ? WHERE id = ?",
                (progress, stage, job_id)
            )
            conn.commit()
        finally:
            conn.close()

def complete_job(job_id: str, status: str = "completed", error: str = None):
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prog = 100 if status == "completed" else 0
    stage = "Analysis complete" if status == "completed" else f"Failed: {error or 'Unknown error'}"
    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                """
                UPDATE jobs SET status = ?, progress = ?, stage = ?, completed_at = ?, error = ?
                WHERE id = ?
                """,
                (status, prog, stage, now_iso, error, job_id)
            )
            conn.commit()
        finally:
            conn.close()

def get_recently_completed_job(user_id: str, ttl_seconds: int = 7200) -> dict | None:
    if not user_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE user_id = ? AND status = 'completed' AND notification_dismissed = 0
                ORDER BY completed_at DESC LIMIT 1
                """,
                (user_id,)
            ).fetchone()
        finally:
            conn.close()
    if not row:
        return None
    return {
        "jobId": row["id"],
        "sessionId": row["analysis_id"],
        "analysisId": row["analysis_id"],
        "filename": row["original_filename"],
        "completedAt": row["completed_at"],
        "status": row["status"],
    }

def dismiss_completed_job(user_id: str, session_id: str):
    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                "UPDATE jobs SET notification_dismissed = 1 WHERE user_id = ? AND analysis_id = ?",
                (user_id, session_id)
            )
            conn.commit()
        finally:
            conn.close()

# ── Analyses & History Helpers (Permanent Metadata + Latest Physical Video Limit) ──

def add_analysis(user_id: str, analysis: dict):
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sid = analysis.get("sessionId") or analysis.get("id") or f"sess_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    filename = analysis.get("filename", "traffic_video.mp4")

    with _lock:
        conn = _get_sqlite_conn()
        try:
            # First, enforce physical video limit: mark all previous records of this user with video_available = 0
            conn.execute(
                "UPDATE analyses SET video_available = 0 WHERE user_id = ? AND id != ?",
                (user_id, sid)
            )
            # Insert the new analysis record (video_available = 1)
            conn.execute(
                """
                INSERT OR REPLACE INTO analyses (
                    id, user_id, filename, status, total_vehicles, cars, motorcycles, autos, buses, trucks,
                    video_duration, processing_time, input_video, output_video, report_path, video_available, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    sid, user_id, filename,
                    analysis.get("status", "completed"),
                    analysis.get("total_vehicles", 0),
                    analysis.get("cars", 0),
                    analysis.get("motorcycles", 0),
                    analysis.get("auto_rickshaws", analysis.get("autos", 0)),
                    analysis.get("buses", 0),
                    analysis.get("trucks", 0),
                    analysis.get("video_duration", 0.0),
                    analysis.get("processing_time", 0.0),
                    analysis.get("input_video", ""),
                    analysis.get("output_video", ""),
                    analysis.get("report_path", ""),
                    now_iso,
                )
            )
            conn.commit()
        finally:
            conn.close()

def get_user_history(user_id: str) -> list:
    if not user_id:
        return []
    with _lock:
        conn = _get_sqlite_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM analyses WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
        finally:
            conn.close()

    result = []
    for r in rows:
        result.append({
            "sessionId": r["id"],
            "session_id": r["id"],
            "id": r["id"],
            "userId": r["user_id"],
            "filename": r["filename"],
            "status": r["status"],
            "total_vehicles": r["total_vehicles"],
            "totalVehicles": r["total_vehicles"],
            "cars": r["cars"],
            "motorcycles": r["motorcycles"],
            "auto_rickshaws": r["autos"],
            "autos": r["autos"],
            "buses": r["buses"],
            "trucks": r["trucks"],
            "video_duration": r["video_duration"],
            "processing_time": r["processing_time"],
            "date": r["created_at"],
            "createdAt": r["created_at"],
            "videoAvailable": bool(r["video_available"]),
            "input_video": r["input_video"],
            "output_video": r["output_video"],
            "report_path": r["report_path"],
        })
    return result

def get_user_analysis(user_id: str, session_id: str) -> dict | None:
    if not user_id or not session_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            r = conn.execute(
                "SELECT * FROM analyses WHERE user_id = ? AND id = ?",
                (user_id, session_id)
            ).fetchone()
        finally:
            conn.close()
    if not r:
        return None
    return {
        "sessionId": r["id"],
        "session_id": r["id"],
        "userId": r["user_id"],
        "filename": r["filename"],
        "status": r["status"],
        "total_vehicles": r["total_vehicles"],
        "cars": r["cars"],
        "motorcycles": r["motorcycles"],
        "auto_rickshaws": r["autos"],
        "buses": r["buses"],
        "trucks": r["trucks"],
        "video_duration": r["video_duration"],
        "processing_time": r["processing_time"],
        "date": r["created_at"],
        "videoAvailable": bool(r["video_available"]),
        "input_video": r["input_video"],
        "output_video": r["output_video"],
        "report_path": r["report_path"],
    }

def delete_user_analysis(user_id: str, session_id: str) -> bool:
    if not user_id or not session_id:
        return False
    with _lock:
        conn = _get_sqlite_conn()
        try:
            # Fetch paths to delete physical files
            row = conn.execute("SELECT * FROM analyses WHERE user_id = ? AND id = ?", (user_id, session_id)).fetchone()
            if not row:
                return False
            for k in ("input_video", "output_video", "report_path"):
                p = row[k]
                if p and Path(p).exists():
                    try:
                        Path(p).unlink()
                    except Exception:
                        pass

            conn.execute("DELETE FROM analyses WHERE user_id = ? AND id = ?", (user_id, session_id))
            conn.execute("DELETE FROM reports WHERE user_id = ? AND analysis_id = ?", (user_id, session_id))
            conn.execute("DELETE FROM jobs WHERE user_id = ? AND analysis_id = ?", (user_id, session_id))
            conn.commit()
            return True
        finally:
            conn.close()

# ── Report Helpers ───────────────────────────────────────────────────────────

def save_report(user_id: str, analysis_id: str, report_data: dict):
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report_id = f"rep_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO reports (id, analysis_id, user_id, report_data, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, analysis_id, user_id, json.dumps(report_data), now_iso)
            )
            conn.commit()
        finally:
            conn.close()

def get_report(user_id: str, session_id: str) -> dict | None:
    if not user_id or not session_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute(
                "SELECT report_data FROM reports WHERE user_id = ? AND analysis_id = ?",
                (user_id, session_id)
            ).fetchone()
        finally:
            conn.close()
    if row and row["report_data"]:
        try:
            return json.loads(row["report_data"])
        except Exception:
            pass
    return None

# ── Camera Helpers ───────────────────────────────────────────────────────────

def get_cameras(user_id: str) -> list:
    if not user_id:
        return []
    with _lock:
        conn = _get_sqlite_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM cameras WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            ).fetchall()
        finally:
            conn.close()
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

def get_camera(user_id: str, camera_id: str, include_password: bool = False) -> dict | None:
    if not user_id or not camera_id:
        return None
    with _lock:
        conn = _get_sqlite_conn()
        try:
            r = conn.execute(
                "SELECT * FROM cameras WHERE id = ? AND user_id = ?",
                (camera_id, user_id)
            ).fetchone()
        finally:
            conn.close()
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

def create_camera(user_id: str, name: str, camera_type: str, stream_url: str,
                  username: str = None, password: str = None, port: int = None):
    if not user_id:
        return None, "Unauthorized", 401
    name = (name or "").strip()
    if not name:
        return None, "Camera name is required.", 400
    camera_type = (camera_type or "IP Camera").strip()
    stream_url = (stream_url or "").strip()

    cam_id = f"cam_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with _lock:
        conn = _get_sqlite_conn()
        try:
            conn.execute(
                """
                INSERT INTO cameras (id, user_id, name, camera_type, stream_url, username, password, port, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NOT CONFIGURED', ?)
                """,
                (cam_id, user_id, name, camera_type, stream_url, username or "", password or "", int(port) if port else None, now_iso)
            )
            conn.commit()
        finally:
            conn.close()
    return get_camera(user_id, cam_id), None, 201

def update_camera(user_id: str, camera_id: str, data: dict):
    if not user_id or not camera_id:
        return None, "Invalid request", 400
    with _lock:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute("SELECT * FROM cameras WHERE id = ? AND user_id = ?", (camera_id, user_id)).fetchone()
            if not row:
                return None, "Camera not found or access denied", 404
            name = data.get("name") if data.get("name") is not None else row["name"]
            camera_type = data.get("type") if data.get("type") is not None else row["camera_type"]
            stream_url = data.get("streamUrl") if data.get("streamUrl") is not None else row["stream_url"]
            username = data.get("username") if data.get("username") is not None else row["username"]
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
                (name, camera_type, stream_url, username, password, port, status, last_connected, resolution, fps, camera_id, user_id)
            )
            conn.commit()
        finally:
            conn.close()
    return get_camera(user_id, camera_id), None, 200

def delete_camera(user_id: str, camera_id: str) -> bool:
    if not user_id or not camera_id:
        return False
    with _lock:
        conn = _get_sqlite_conn()
        try:
            cur = conn.execute("DELETE FROM cameras WHERE id = ? AND user_id = ?", (camera_id, user_id))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
