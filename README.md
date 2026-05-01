# 🖥️ Carbonpulse — Real-Time System Monitoring

A lightweight, multi-client system monitoring suite for Windows. A central server collects live CPU, RAM, GPU, power, carbon emission, and process data from remote clients and displays everything through a sleek web dashboard. A separate client-side dashboard lets each monitored machine view its own stats and communicate with the server.

---

## 📸 Dashboards

| Server Dashboard | Client Dashboard |
|---|---|
| View all connected clients, kill processes, broadcast messages | View own stats, hardware info, message server & other clients |

---

## 🗂️ File Overview

| File | Role |
|---|---|
| `server.py` | Central server — TCP + WebSocket hub |
| `client.py` | Silent background agent running on each monitored machine |
| `detail2.py` | Fast binary serialization of process & metrics data |
| `hardware.py` | Hardware detection (CPU, GPU, RAM, Disk) |
| `server_dashboard.html` | **Server** web dashboard (open on the server machine) |
| `client_dashboard.html` | **Client** web dashboard (open on the monitored machine) |

---

## ⚙️ How It Works

```
┌──────────────────────────────────────────────────┐
│                   SERVER MACHINE                 │
│                                                  │
│  server_improved.py          dashboard.html      │
│  ├── TCP  :9000  (chat)   ←→  WebSocket :9999   │
│  ├── TCP  :8000  (metrics)                       │
│  ├── TCP  :8888  (hardware)                      │
│  └── WS   :9999  (dashboard)                     │
└──────────────┬───────────────────────────────────┘
               │  Network
┌──────────────▼───────────────────────────────────┐
│                  CLIENT MACHINE                  │
│                                                  │
│  client_improved.py          client_dashboard.html│
│  ├── connects :9000  (chat)    connects :9999    │
│  ├── connects :8000  (metrics)                   │
│  └── connects :8888  (hardware)                  │
└──────────────────────────────────────────────────┘
```

Each client opens **three TCP connections** to the server:
- **Port 9000** — chat & command channel (receives kill signals, messages)
- **Port 8000** — binary metrics stream (CPU/RAM/GPU/processes every 3 seconds)
- **Port 8888** — hardware info (sent once on connect, refreshed every 10 minutes)

The server exposes a **WebSocket on port 9999** that both dashboards connect to for live updates.

---

## 🚀 Installation

### Requirements

```bash
pip install psutil GPUtil pywin32 py-cpuinfo pyopencl websockets
```

> **Note:** `pyopencl` is used for AMD/Intel GPU detection. If you don't have an OpenCL-capable GPU, it will gracefully report no OpenCL device found.

### Python Version

Python 3.9+ recommended.

---

## 🖥️ Running the Server

Run on the central monitoring machine:

```bash
python server.py
```

Then open `server_dashboard.html` in a browser on the same machine. The dashboard connects to `ws://127.0.0.1:9999` by default.

---

## 💻 Running the Client Agent

Run on each machine you want to monitor. Edit the `SERVER_IP` at the top of the file first:

```python
# client.py
SERVER_IP = "192.168.1.100"   # ← set to your server's IP
```

Then run:

```bash
python client.py
```

The client runs **silently** — no terminal output, no UI. All interaction happens through the dashboards.

To run it automatically on Windows startup, add it as a Task Scheduler entry or a Windows Service.

---

## 🌐 Opening the Dashboards

### Server Dashboard (`server_dashboard.html`)

Open directly in any browser on the server machine. No web server needed — it's a standalone HTML file.

The dashboard connects to `ws://127.0.0.1:9999` automatically.

**Features:**
- Live CPU / RAM / GPU / Power / CO₂ gauges per client
- Process table with one-click kill for any client
- Hardware info panel per client
- Chat — broadcast to all clients or private message a specific client
- Total power consumption and carbon emission across all clients

### Client Dashboard (`client_dashboard.html`)

Open in a browser on the **monitored machine**. On first open, a setup overlay asks for:

1. **WebSocket URL** — the server address, e.g. `ws://192.168.1.100:9999`
2. **Client ID (CID)** — your assigned ID, visible in the server dashboard when you connect

**Features:**
- Your own live gauges (CPU, RAM, GPU, Power, CO₂)
- Your own process list with live search/filter
- Your own hardware info
- Messaging panel — send public or private messages:
  - **Everyone (Public)** — visible to all dashboards
  - **Server (Private)** — seen only in server dashboard
  - **Client #N (Private)** — seen only by that specific client

---

## 📡 Network Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 9000 | TCP | Chat & command channel |
| 8000 | TCP | Binary metrics stream |
| 8888 | TCP | Hardware info JSON |
| 9999 | WebSocket | Dashboard real-time updates |

Make sure these ports are open in your firewall if monitoring across a network.

---

## 📊 Metrics & Data

### What Gets Collected (every 3 seconds)

- CPU usage %
- RAM usage %
- GPU usage % (NVIDIA via GPUtil)
- Estimated power draw (W) — calculated from CPU/RAM/GPU load
- Estimated CO₂ emission (g/s) — based on power × carbon intensity factor
- List of all visible (windowed) processes with PID and name

### Hardware Info (on connect, every 10 min)

- CPU — name, architecture, threads, vendor, clock speed
- GPU — NVIDIA (via GPUtil) and OpenCL devices (AMD/Intel)
- RAM — total, used, free, swap
- Disks — all partitions with total/used/free

---

## 🔧 Configuration

### Client (`client.py`)

```python
SERVER_IP     = "127.0.0.1"   # Server IP address
MSG_PORT      = 9000           # Chat port
DATA_PORT     = 8000           # Metrics port
HARD_PORT     = 8888           # Hardware port
RECONNECT_SEC = 5              # Seconds between reconnect attempts
```

### Power & Emission Formula (`detail2.py`)

```python
power    = (50 * cpu/100) + (10 * ram/100) + (95 * gpu/100)   # Watts
emission = (power * 0.70) / 3600                               # g CO₂ per second
```

Adjust the coefficients to match your hardware's actual TDP.

---

## 🗃️ Project Structure

```
syswatch/
├── server.py                # Server (run on monitoring machine)
├── client.py                # Client agent (run on each target machine)
├── detail2.py               # Metrics serialization/deserialization
├── hardware.py              # Hardware detection
├── server_dashboard.html    # Server web dashboard
├── client_dashboard.html    # Client web dashboard
└── README.md
```

---

## ⚠️ Known Limitations

- **Windows only** — `pywin32` and the visible-window process filter are Windows-specific. The hardware and metrics modules would need adaptation for Linux/macOS.
- **Process visibility** — only processes with a visible window are listed (by design, to reduce noise). Background services are excluded.
- **Power estimation** — the power draw formula is an approximation based on load percentages, not actual hardware sensor readings.
- **No authentication** — the WebSocket server has no auth. Use on a trusted local network only.

---

## 📄 License

MIT — free to use, modify, and distribute.
