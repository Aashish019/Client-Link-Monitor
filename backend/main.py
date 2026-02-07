import asyncio
import psutil
import httpx
import json
import logging
import aiosqlite
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

import os
from pythonjsonlogger import jsonlogger

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
JSON_LOGS = os.getenv("JSON_LOGS", "true").lower() == "true"

handler = logging.StreamHandler()
if JSON_LOGS:
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    handler.setFormatter(formatter)

logging.basicConfig(level=LOG_LEVEL, handlers=[handler])
logger = logging.getLogger(__name__)

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Global HTTPX client with optimized connection pooling
http_client = httpx.AsyncClient(
    limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    timeout=httpx.Timeout(10.0, connect=5.0),
)

# Configuration
DATA_DIR = os.getenv("DATA_DIR", ".")
CLIENTS_FILE = os.path.join(DATA_DIR, "clients.json")
URL_CHECK_INTERVAL = int(os.getenv("URL_CHECK_INTERVAL", "180"))
SYSTEM_CHECK_INTERVAL = int(os.getenv("SYSTEM_CHECK_INTERVAL", "1"))
MAX_CONCURRENT_CHECKS = int(os.getenv("MAX_CONCURRENT_CHECKS", "10"))
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "")
DB_FILE = os.path.join(DATA_DIR, "monitor.db")

# Ensure data directory exists
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# Database Helpers
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS clients (name TEXT PRIMARY KEY, url TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS status_checks (name TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, status TEXT)"
        )
        await db.commit()

        # Data Migration Logic
        cursor = await db.execute("SELECT COUNT(*) FROM clients")
        count = (await cursor.fetchone())[0]

        if count == 0 and os.path.exists(CLIENTS_FILE):
            logger.info("Migrating data from clients.json to SQLite...")
            try:
                with open(CLIENTS_FILE, "r") as f:
                    clients = json.load(f)
                    for name, url in clients.items():
                        await db.execute(
                            "INSERT OR IGNORE INTO clients (name, url) VALUES (?, ?)",
                            (name, url),
                        )
                await db.commit()
                logger.info("Migration successful.")
            except Exception as e:
                logger.error(f"Migration failed: {e}")


async def get_db_clients() -> Dict[str, str]:
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT name, url FROM clients") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


async def add_db_client(name: str, url: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT OR REPLACE INTO clients (name, url) VALUES (?, ?)", (name, url)
        )
        await db.commit()


async def remove_db_client(name: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("DELETE FROM clients WHERE name = ?", (name,))
        await db.execute("DELETE FROM status_checks WHERE name = ?", (name,))
        await db.commit()


async def log_check(name: str, status: str):
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(
            "INSERT INTO status_checks (name, status) VALUES (?, ?)", (name, status)
        )
        await db.commit()


async def get_uptime_stats(name: str) -> Dict[str, float]:
    """Calculate uptime percentage for 24h and 7d."""
    async with aiosqlite.connect(DB_FILE) as db:
        # Last 24h
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'up') * 100.0 / COUNT(*)
            FROM status_checks 
            WHERE name = ? AND timestamp >= datetime('now', '-1 day')
            """,
            (name,),
        )
        uptime_24h = (await cursor.fetchone())[0] or 100.0

        # Last 7d
        cursor = await db.execute(
            """
            SELECT 
                COUNT(*) FILTER (WHERE status = 'up') * 100.0 / COUNT(*)
            FROM status_checks 
            WHERE name = ? AND timestamp >= datetime('now', '-7 days')
            """,
            (name,),
        )
        uptime_7d = (await cursor.fetchone())[0] or 100.0

        return {"24h": round(uptime_24h, 2), "7d": round(uptime_7d, 2)}


# In-memory sync of clients (to avoid querying DB on every interval)
CLIENT_URLS: Dict[str, str] = {}


# State
class GlobalState:
    system_stats: Dict[str, Any] = {}
    url_statuses: List[Dict[str, Any]] = []
    # To track previous status for alerting
    previous_url_statuses: Dict[str, str] = {}


state = GlobalState()


# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send immediate initial state
        await websocket.send_json(self.get_payload())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self):
        payload = self.get_payload()
        for connection in self.active_connections:
            try:
                await connection.send_json(payload)
            except Exception:
                pass

    def get_payload(self):
        return {
            "type": "update",
            "system": state.system_stats,
            "urls": state.url_statuses,
        }


manager = ConnectionManager()


# Background Tasks
async def monitor_system():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            net = psutil.net_io_counters()

            state.system_stats = {
                "cpu": cpu,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": disk.percent,
                },
                "net": {"sent": net.bytes_sent, "recv": net.bytes_recv},
            }
            await manager.broadcast()
        except Exception as e:
            logger.error(f"System monitor error: {e}")
        await asyncio.sleep(SYSTEM_CHECK_INTERVAL)


async def check_single_url(client: httpx.AsyncClient, name: str, url: str):
    try:
        response = await client.head(url, timeout=10.0, follow_redirects=True)
        is_up = 200 <= response.status_code < 400
        status = "up" if is_up else "down"
        return {
            "name": name,
            "url": url,
            "status": status,
            "status_code": response.status_code,
            "error": None,
        }
    except Exception as e:
        result = {
            "name": name,
            "url": url,
            "status": "down",
            "status_code": 0,
            "error": str(e),
        }
    
    # Log result to DB asynchronously
    asyncio.create_task(log_check(name, result["status"]))
    
    # Trigger alert if transitioning to down
    if result["status"] == "down" and state.previous_url_statuses.get(name) != "down":
        asyncio.create_task(trigger_n8n_alert(name, url, result["error"] or "Status check failed"))
    
    state.previous_url_statuses[name] = result["status"]
    return result


async def trigger_n8n_alert(name: str, url: str, error_detail: str):
    if not N8N_WEBHOOK_URL:
        logger.warning(
            f"No n8n Webhook URL set. Would alert for {name} ({url}) - {error_detail}"
        )
        return

    try:
        payload = {
            "name": name,
            "url": url,
            "status": 500,  # Providing 500 as per user example for down
            "error": {
                "status": "500",
                "detail": error_detail,
            },  # Matching structure
        }
        await http_client.post(N8N_WEBHOOK_URL, json=payload)
        logger.info(f"Triggered n8n webhook for {name}")
    except Exception as e:
        logger.error(f"Failed to trigger n8n: {e}")


async def monitor_urls():
    while True:
        logger.info("Starting URL checks...")
        await monitor_urls_once()
        # Wait for next interval
        await asyncio.sleep(URL_CHECK_INTERVAL)


@app.post("/api/refresh")
async def refresh_checks():
    await monitor_urls_once()
    return {"status": "refreshing"}


@app.post("/api/restart/{name}")
async def manual_restart(name: str):
    url = CLIENT_URLS.get(name)
    if not url:
        return {"error": "Service not found"}

    # Trigger n8n webhook manually
    # We send status 500 to simulate "down" so n8n runs the restart logic
    asyncio.create_task(trigger_n8n_alert(name, url, "Manual Restart Triggered"))
    return {"status": "restart_triggered", "name": name}


# Client Management
class Client(BaseModel):
    name: str
    url: str


@app.post("/api/clients")
async def add_client(client: Client):
    await add_db_client(client.name, client.url)
    global CLIENT_URLS
    CLIENT_URLS = await get_db_clients()

    # Trigger immediate check for new client
    asyncio.create_task(monitor_urls_once())

    return {"status": "added", "client": client}


@app.post("/api/clients/import")
async def import_clients(clients: Dict[str, str]):
    for name, url in clients.items():
        await add_db_client(name, url)
    
    global CLIENT_URLS
    CLIENT_URLS = await get_db_clients()
    asyncio.create_task(monitor_urls_once())

    return {"status": "imported", "count": len(clients)}


@app.delete("/api/clients/{name}")
async def delete_client(name: str):
    await remove_db_client(name)
    global CLIENT_URLS
    CLIENT_URLS = await get_db_clients()

    # Update global state immediately
    state.url_statuses = [u for u in state.url_statuses if u["name"] != name]
    await manager.broadcast()

    return {"status": "deleted", "name": name}

    # Update global state immediately
    state.url_statuses = [u for u in state.url_statuses if u["name"] != name]
    await manager.broadcast()

    return {"status": "deleted", "name": name}


async def monitor_urls_once():
    # Helper to run logic outside of loop
    tasks = [
        check_single_url(http_client, name, url) for name, url in CLIENT_URLS.items()
    ]
    check_results = await asyncio.gather(*tasks)

    # Attach uptime stats to results
    final_results = []
    for res in check_results:
        stats = await get_uptime_stats(res["name"])
        res["uptime"] = stats
        final_results.append(res)

    final_results.sort(key=lambda x: 0 if x["status"] == "down" else 1)
    state.url_statuses = final_results
    await manager.broadcast()

    await manager.broadcast()


@app.on_event("startup")
async def startup_event():
    logger.info("Startup complete")
    await init_db()
    global CLIENT_URLS
    CLIENT_URLS = await get_db_clients()
    asyncio.create_task(monitor_system())
    asyncio.create_task(monitor_urls())


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Closing HTTP client")
    await http_client.aclose()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.get("/")
def read_root():
    return {"status": "ok", "service": "Butter Smooth Monitor"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "system": {
            "cpu": state.system_stats.get("cpu"),
            "memory": state.system_stats.get("memory", {}).get("percent"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    HOST = os.getenv("HOST", "0.0.0.0")  # nosec B104
    PORT = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host=HOST, port=PORT)
