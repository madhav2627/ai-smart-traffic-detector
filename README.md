# AI-Based Intelligent Traffic Detection and Analysis System

[![Vercel Deployment](https://img.shields.io/badge/Vercel-100%25%20Online%20Deployed-black?logo=vercel)](https://ai-smart-traffic-detector.vercel.app)
[![Model](https://img.shields.io/badge/Detector-UVH--26%20YOLOv11--S-blue)]()
[![Tracker](https://img.shields.io/badge/Tracker-ByteTrack%20Multi--Object-emerald)]()
[![Platform](https://img.shields.io/badge/Architecture-Vercel%20Serverless%20Python-blue)]()

An enterprise-grade, state-of-the-art intelligent traffic surveillance and vehicle analytics platform. Engineered for urban intersections, highway corridors, and online video analysis — running 100% online on Vercel without local server dependencies.

---

## 🌟 Key Highlights

- **100% Online Vercel Deployment**: No local PC backend, no START.bat, no localhost:5000, no tunneling or PC dependencies required. Everything runs directly from `https://ai-smart-traffic-detector.vercel.app`.
- **Real IISc UVH-26 YOLOv11-S Vehicle Detector**: Bundled `vehicle_traffic.pt` model detects 14 Indian traffic classes normalized to 5 core dashboard classes:
  - 🚙 **Cars** (Sedans, Hatchbacks, SUVs, MUVs, Vans)
  - 🏍️ **Motorcycles** (Bikes, Scooters, Two-wheelers)
  - 🛺 **Auto-Rickshaws** (Three-wheelers)
  - 🚌 **Buses** (Transit, Intercity, Mini-buses, Tempo Travellers)
  - 🚛 **Trucks** (Freight, Multi-axle, LCVs)
- **ByteTrack Multi-Object Tracking**: Real unique vehicle identity tracking across video frames with Kalman filtering and trajectory motion analysis (NO line-crossing gimmicks, NO fake counts).
- **Asynchronous Job-Based Processing**: Browser can navigate freely between Dashboard, Surveillance, Analytics, Traffic AI, History, and Reports while server-side processing runs independently.
- **Global Processing Indicator**: Real-time status badge visible across all authenticated pages.
- **Strict User Isolation**: Every record (`analyses`, `jobs`, `reports`, `cameras`) is permanently scoped to `userId`. Zero data leakage between accounts.
- **Permanent History & 1-Video Retention**: Preserves unlimited historical analytical metadata while keeping physical storage lean (max 1 physical retained video per user).

---

## 📐 Architecture

```
Browser
   ↓
Vercel Cloud Platform
   ├── Static Frontend (/frontend)
   │     ├── Dashboard, Surveillance, Analytics, History, Reports, Cameras
   │     └── Design System & Shell Navigation
   │
   ├── Serverless API (/api/index.py)
   │     ├── Authentication & User Isolation (/api/auth/*)
   │     ├── Video Upload & Job Orchestration (/api/analyze, /api/active-job)
   │     ├── Camera Connectivity & Reachability Probing (/api/cameras/*)
   │     └── Storage Management (/api/storage/*)
   │
   ├── Persistent Server-Side Database (/api/db.py)
   │     └── Per-user isolated storage for users, analyses, jobs, reports, cameras
   │
   └── AI Detection & Tracking Engine (/api/detector.py)
         ├── IISc UVH-26 YOLOv11-S Model (vehicle_traffic.pt)
         ├── 14 → 5 Indian Traffic Class Normalization
         ├── ByteTrack Unique Vehicle Tracking
         ├── Congestion Density & Relative Speed Estimation
         └── Web-Ready Video & JSON Report Generation
```

---

## 🚀 Deployment

The repository is configured for automatic Vercel continuous deployment:

```bash
git push origin main
```

Vercel builds the Python Serverless Function in `/api/index.py`, routes all `/api/*` endpoints, serves the frontend from `/frontend`, and applies security headers automatically via `vercel.json`.

---

## 📄 License
This project is released under the MIT License.
