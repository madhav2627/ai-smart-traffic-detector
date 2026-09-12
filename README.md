# AI-Based Intelligent Traffic Detection and Analysis System

[![Vercel Deployment](https://img.shields.io/badge/Vercel-Deploy%20Ready-black?logo=vercel)](https://vercel.com)
[![Model](https://img.shields.io/badge/Detector-UVH--26%20YOLOv11--S-blue)]()
[![Tracker](https://img.shields.io/badge/Tracker-ByteTrack%20Multi--Object-emerald)]()
[![Inference](https://img.shields.io/badge/Inference-100%25%20Local-green)]()
[![Platform](https://img.shields.io/badge/Platform-Web%20Console-blue)]()

An enterprise-grade, state-of-the-art intelligent traffic surveillance and vehicle analytics platform. Engineered for high-density urban intersections, highway corridors, and live CCTV feeds.

---

## 🌟 Key Highlights

- **Five Specialized Vehicle Classes**: Highly accurate detection for Indian and global mixed traffic:
  - 🚙 **Cars** (Sedans, Hatchbacks, SUVs)
  - 🏍️ **Motorcycles** (Bikes, Scooters)
  - 🛺 **Auto-Rickshaws** (Three-wheelers)
  - 🚌 **Buses** (Transit, Intercity)
  - 🚛 **Trucks** (Freight, Multi-axle)
- **ByteTrack Multi-Object Tracking**: Persistent trajectory tracking across frames with trajectory occlusion handling and ID reassignment prevention.
- **Traffic Density Engine**: Automatic real-time congestion classification (`LOW`, `MEDIUM`, `HIGH`, `SEVERE`) derived from active vehicle spatial occupancy.
- **Live CCTV Connectivity**:
  - RTSP Streams (`rtsp://username:password@ip:port/h264`)
  - IP Cameras & Webcams (`http://ip:port/video`)
  - USB Cameras (`/dev/video0` or device index `0`)
  - Real-time connection probing and threaded MJPEG annotated live streams.
- **Natural Language Traffic AI**: Ask questions about your traffic sessions (e.g. *"What was peak congestion?"*, *"How many heavy vehicles were tracked?"*).
- **Forensic Report Generation**: One-click download of comprehensive forensic PDF reports and raw JSON analytical datasets.
- **100% Private Local Inference**: Zero third-party cloud dependencies; all video frames stay strictly on your local hardware.

---

## 📐 Architecture & Technology Stack

```
AI-BASED-INTELLIGENT-TRAFFIC-DETECTION-AND-ANALYSIS/
├── frontend/                     # Modern Vanilla CSS & JS Web Application
│   ├── index.html                # High-conversion Landing Page & Cockpit Preview
│   ├── login.html                # Secure Authentication Portal
│   ├── register.html             # User Registration
│   ├── pages/                    # Authenticated Application Views
│   │   ├── dashboard.html        # Fleet Overview & Real-time Metrics
│   │   ├── surveillance.html     # AI Video & Live CCTV Analysis Console
│   │   ├── cameras.html          # Live CCTV Stream Management
│   │   ├── live.html             # Real-time Camera Feeds Grid
│   │   ├── analytics.html        # Forensic Vehicle Analytics
│   │   ├── traffic-ai.html       # Natural Language Traffic Assistant
│   │   ├── history.html          # Analysis Session Records
│   │   ├── reports.html          # Executive Forensic Summaries
│   │   └── settings.html         # Configuration, Storage & Endpoints
│   ├── css/                      # Modular Dark Theme Design System
│   └── js/                       # Unified Shell, Auth & API Client
├── backend/                      # Python Flask Server & Surveillance Engine
│   ├── server.py                 # Multi-user API, RTSP Prober & MJPEG Streamer
│   └── requirements_backend.txt  # Lightweight Web Service Dependencies
├── traffic_ai_complete_improved/ # AI Detection & Tracking Pipeline
│   ├── main.py                   # YOLOv11 / YOLOv9 + ByteTrack Video Processor
│   ├── vehicle_traffic.pt        # Trained Vehicle Detection Weights
│   └── requirements.txt          # PyTorch & Ultralytics Dependencies
├── storage/                      # Isolated Multi-user Local Storage
├── vercel.json                   # Vercel Deployment Configuration
└── START.bat                     # 1-Click Windows Launch Script
```

---

## 🚀 Deployment Options

### Option 1: Deploy Frontend to Vercel (Recommended for Web Access)

This project includes a native `vercel.json` for 1-click deployment to Vercel:

1. Fork or import this repository into your [Vercel Dashboard](https://vercel.com/new).
2. Keep the default settings (Vercel automatically detects `outputDirectory: "frontend"` and root URL rewrites from `vercel.json`).
3. Click **Deploy**.
4. Once deployed, open your Vercel URL (e.g. `https://your-traffic-app.vercel.app`).
5. In **Settings > System Information**, you can optionally enter your local or remote inference endpoint (e.g., `http://192.168.0.x:5000` or cloud worker URL) to stream live camera analytics directly into your hosted dashboard!

---

### Option 2: Run Locally (Full System with AI Inference)

#### Prerequisites
- Python 3.10+
- (Optional) NVIDIA GPU with CUDA for ultra-fast real-time inference

#### 1-Click Launch (Windows)
Double-click `START.bat` in the project root. It will:
- Check your Python environment.
- Install backend and detector dependencies.
- Launch the Flask server at `http://127.0.0.1:5000` (and on your local Wi-Fi IP `http://192.168.x.x:5000`).
- Automatically open your default browser.

#### Manual Terminal Launch
```bash
# 1. Install dependencies
pip install -r backend/requirements_backend.txt
pip install -r traffic_ai_complete_improved/requirements.txt

# 2. Launch the server
python backend/server.py
```
Visit `http://localhost:5000` in your web browser.

---

## 🔒 Security & Privacy

- **User Isolation**: Multi-tenant architecture with per-user data isolation and salted SHA-256 password hashing.
- **Physical Video Retention**: Configured with a default single-video retention policy to prevent hard drive bloat while permanently preserving all forensic analytical metadata.
- **CORS Enabled**: Robust cross-origin support enabling secure communication between Vercel-hosted frontends and private on-premises inference servers.

---

## 📄 License
This project is released under the MIT License.
