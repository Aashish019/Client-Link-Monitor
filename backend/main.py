import asyncio
import psutil
import httpx
import json
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
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

# Configuration
URL_CHECK_INTERVAL = 180  # 3 minutes
SYSTEM_CHECK_INTERVAL = 1  # 1 second
MAX_CONCURRENT_CHECKS = 10
N8N_WEBHOOK_URL = "https://n8n.mcmillan.solutions/webhook/monitor-alert"  # User to provide or we'll mock/log for now if not set

# Client List
def load_clients():
    try:
        with open("clients.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("clients.json not found!")
        return {}
    except json.JSONDecodeError:
        logger.error("Invalid JSON in clients.json")
        return {}

CLIENT_URLS = load_clients()

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
            "urls": state.url_statuses
        }

manager = ConnectionManager()

# Background Tasks
async def monitor_system():
    while True:
        try:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net = psutil.net_io_counters()

            state.system_stats = {
                "cpu": cpu,
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "net": {
                    "sent": net.bytes_sent,
                    "recv": net.bytes_recv
                }
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
            "error": None
        }
    except Exception as e:
        return {
            "name": name, 
            "url": url, 
            "status": "down", 
            "status_code": 0,
            "error": str(e)
        }

async def trigger_n8n_alert(name: str, url: str, error_detail: str):
    if not N8N_WEBHOOK_URL:
        logger.warning(f"No n8n Webhook URL set. Would alert for {name} ({url}) - {error_detail}")
        return
    
    async with httpx.AsyncClient() as client:
        try:
            payload = {
                "name": name,
                "url": url,
                "status": 500, # Providing 500 as per user example for down
                "error": {"status": "500", "detail": error_detail} # Matching structure
            }
            await client.post(N8N_WEBHOOK_URL, json=payload)
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
    asyncio.create_task(trigger_n8n_alert(
        name, 
        url, 
        "Manual Restart Triggered"
    ))
    return {"status": "restart_triggered", "name": name}

# Client Management
from pydantic import BaseModel

class Client(BaseModel):
    name: str
    url: str

def save_clients(clients: Dict[str, str]):
    try:
        with open("clients.json", "w") as f:
            json.dump(clients, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save clients: {e}")

@app.post("/api/clients")
async def add_client(client: Client):
    if client.name in CLIENT_URLS:
        return {"error": "Client already exists", "status": "error"}
    
    CLIENT_URLS[client.name] = client.url
    save_clients(CLIENT_URLS)
    
    # Trigger immediate check for new client
    asyncio.create_task(monitor_urls_once())
    
    return {"status": "added", "client": client}

@app.post("/api/clients/import")
async def import_clients(clients: Dict[str, str]):
    count = 0
    for name, url in clients.items():
        CLIENT_URLS[name] = url
        count += 1
    
    save_clients(CLIENT_URLS)
    asyncio.create_task(monitor_urls_once())
    
    return {"status": "imported", "count": count}

@app.delete("/api/clients/{name}")
async def delete_client(name: str):
    if name not in CLIENT_URLS:
        return {"error": "Client not found", "status": "error"}
    
    del CLIENT_URLS[name]
    save_clients(CLIENT_URLS)
    
    # Update global state immediately
    state.url_statuses = [u for u in state.url_statuses if u['name'] != name]
    await manager.broadcast()
    
    return {"status": "deleted", "name": name}

async def monitor_urls_once():
    # Helper to run logic outside of loop
    async with httpx.AsyncClient(verify=False) as client:
        tasks = [check_single_url(client, name, url) for name, url in CLIENT_URLS.items()]
        results = await asyncio.gather(*tasks)

    results.sort(key=lambda x: 0 if x['status'] == 'down' else 1)
    state.url_statuses = results
    
    # Alerting logic (duplicated from loop, could be refactored)
    # Alerting logic - DISABLED automatic triggers per user request
    # for res in results:
    #     if res['status'] == 'down':
    #          asyncio.create_task(trigger_n8n_alert(
    #             res['name'], 
    #             res['url'], 
    #             res['error'] or f"HTTP {res['status_code']}"
    #         ))

    await manager.broadcast()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(monitor_system())
    asyncio.create_task(monitor_urls())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # Keep connection alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"status": "ok", "service": "Butter Smooth Monitor"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
