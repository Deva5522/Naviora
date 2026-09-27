import time
import requests
import threading

API_URL = "http://localhost:8000/api/v1/telemetry"

# Route: Kattanam Church Junction -> Karimulakal -> Charummoodu -> St. Thomas College, Chengannur
WAYPOINTS = [
    {"lat": 9.1352, "lng": 76.5338}, # Kattanam Church Junction (Updated Start)
    {"lat": 9.1440, "lng": 76.5370},
    {"lat": 9.1550, "lng": 76.5410}, # Karimulakal
    {"lat": 9.1630, "lng": 76.5450},
    {"lat": 9.1720, "lng": 76.5505}, # Charummoodu
    {"lat": 9.2000, "lng": 76.5700},
    {"lat": 9.2500, "lng": 76.5900},
    {"lat": 9.3175, "lng": 76.6120}  # St. Thomas College, Chengannur
]

def run_simulation(bus_id: str, waypoints: list, speed: float, interval: float):
    print(f"[*] Started simulation for {bus_id}")
    while True:
        for point in waypoints:
            payload = {
                "bus_id": bus_id,
                "latitude": point["lat"],
                "longitude": point["lng"],
                "speed": speed
            }
            try:
                res = requests.post(API_URL, json=payload, timeout=2)
                print(f"Ping {bus_id}: Lat {point['lat']}, Lng {point['lng']} | Status: {res.status_code}")
            except Exception as e:
                print(f"[!] Error pinging {bus_id}: {e}")
            time.sleep(interval)

if __name__ == "__main__":
    # BUS-06: Kattanam Church -> St. Thomas College
    t1 = threading.Thread(target=run_simulation, args=("BUS-06", WAYPOINTS, 38.5, 2.0))
    # BUS-02: St. Thomas College -> Kattanam Church (Reverse Route)
    t2 = threading.Thread(target=run_simulation, args=("BUS-02", list(reversed(WAYPOINTS)), 42.0, 2.5))

    t1.daemon = True
    t2.daemon = True

    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bus simulator...")