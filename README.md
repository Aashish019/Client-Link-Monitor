# Client Link Monitor

A high-performance, real-time infrastructure and service health monitoring dashboard. This application provides a sleek UI to track system resources and monitor the availability of multiple client services.

## 🚀 Features

- **Real-time Monitoring**: Uses WebSockets to provide live updates on system stats and service health.
- **System Metrics**: Tracks CPU usage, RAM, Disk space, and Network I/O in real-time.
- **Service Health Checks**: Periodically verifies the status of configured URLs (up/down).
- **Client Management**:
  - Add new services dynamically via the dashboard.
  - Delete services with a single click.
  - Bulk import services from a JSON file.
- **n8n Integration**: Built-in support for triggering n8n webhooks for alerts and automated service restarts.
- **Modern UI/UX**: Premium dashboard built with React, Tailwind CSS, and Framer Motion for smooth transitions and glassmorphism aesthetics.

## 🛠️ Tech Stack

### Backend
- **FastAPI**: High-performance Python web framework.
- **WebSockets**: For real-time data broadcasting.
- **Httpx**: Modern HTTP client for async health checks.
- **Psutil**: System resource monitoring.
- **Uvicorn**: ASGI server implementation.

### Frontend
- **React**: Component-based UI library.
- **Vite**: Ultra-fast build tool and dev server.
- **TypeScript**: Type-safe development.
- **Tailwind CSS**: Modern utility-first styling.
- **Framer Motion**: Premium animations.
- **Lucide React**: Clean and consistent iconography.

## 📦 Getting Started

The easiest way to run the application is using Docker.

### Prerequisites
- Docker and Docker Compose installed.

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Aashish019/Client-Link-Monitor.git
   cd Client-Link-Monitor
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up -d --build
   ```

3. **Access the Dashboard**:
   Open [http://localhost:5174](http://localhost:5174) in your browser.

## ⚙️ Configuration

- **Backend Port**: 8000
- **Frontend Port**: 5174
- **Webhook Configuration**: Set the `N8N_WEBHOOK_URL` environment variable in `docker-compose.yml` to enable automated alerts and restarts.

## 📄 License

This project is licensed under the MIT License.

---
Created by Aashish
