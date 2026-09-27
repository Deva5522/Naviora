import sqlite3
from math import radians, cos, sin, asin, sqrt
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Database Setup ---
conn = sqlite3.connect("telemetry.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS bus_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bus_id TEXT,
    latitude REAL,
    longitude REAL,
    speed REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# --- Geofence Bus Stops (Updated Kattanam Church Stop) ---
STOPS = [
    {"name": "Kattanam Junction (Near Church)", "lat": 9.1352, "lng": 76.5338, "radius_m": 300},
    {"name": "Karimulakal", "lat": 9.1550, "lng": 76.5410, "radius_m": 300},
    {"name": "Charummoodu", "lat": 9.1720, "lng": 76.5505, "radius_m": 300},
    {"name": "St. Thomas College, Chengannur", "lat": 9.3175, "lng": 76.6120, "radius_m": 300}
]

def haversine_meters(lat1, lon1, lat2, lon2):
    r = 6371000
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi/2)**2 + cos(phi1)*cos(phi2)*sin(dlambda/2)**2
    return r * 2 * asin(sqrt(a))

class Telemetry(BaseModel):
    bus_id: str
    latitude: float
    longitude: float
    speed: float

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(data)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

@app.post("/api/telemetry")
@app.post("/api/v1/telemetry")
async def receive_telemetry(data: Telemetry):
    # 1. Log to SQLite
    cursor.execute(
        "INSERT INTO bus_logs (bus_id, latitude, longitude, speed) VALUES (?, ?, ?, ?)",
        (data.bus_id, data.latitude, data.longitude, data.speed)
    )
    conn.commit()

    # 2. Geofence Check, Distance, and ETA Calculation
    near_stop = None
    next_stop_info = None
    min_dist = float("inf")

    for stop in STOPS:
        dist_m = haversine_meters(data.latitude, data.longitude, stop["lat"], stop["lng"])
        
        # Geofence check
        if dist_m <= stop["radius_m"]:
            near_stop = f"Arriving at {stop['name']} ({int(dist_m)}m away)"

        # Find closest stop for ETA calculation
        if dist_m < min_dist:
            min_dist = dist_m
            speed_m_per_sec = (data.speed * 1000) / 3600 if data.speed > 0 else 0
            eta_mins = round((dist_m / speed_m_per_sec) / 60, 1) if speed_m_per_sec > 0 else "N/A"
            next_stop_info = {
                "name": stop["name"],
                "distance_km": round(dist_m / 1000, 2),
                "eta_mins": eta_mins
            }

    payload = data.model_dump() if hasattr(data, "model_dump") else data.dict()
    payload["stop_alert"] = near_stop
    payload["next_stop"] = next_stop_info

    # 3. Broadcast to Web Dashboard
    await manager.broadcast(payload)
    return {"status": "success"}

@app.websocket("/ws/bus-stream")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)