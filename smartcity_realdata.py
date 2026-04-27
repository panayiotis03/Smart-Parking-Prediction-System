import requests
import sqlite3
import time
from datetime import datetime
import random

TFL_KEY = "dad0400bba354bdea4898dabf6167f22"
TOMTOM_KEY = "K6LFXx456fgf2nWMmEJqx75Fl9h3CTXh"

def init_db():
    conn = sqlite3.connect('london_smart_parking.db')
    cursor = conn.cursor()
    # Δημιουργία του πίνακα αν δεν υπάρχει
    cursor.execute('''CREATE TABLE IF NOT EXISTS parking_logs 
        (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, parking_name TEXT, 
        free_spaces INTEGER, traffic_speed REAL, temperature REAL, weather_desc TEXT,
        lat REAL, lon REAL)''')
    conn.commit()
    conn.close()
    
def get_weather_desc(code):
    if code == 0:
        return "Clear"

    elif code in [1, 2]:
        return "Partly Cloudy"

    elif code == 3:
        return "Cloudy"

    elif code in [45, 48]:
        return "Fog"

    elif code in [51, 53, 55]:
        return "Drizzle"

    elif code in [61, 63, 65, 80, 81, 82]:
        return "Rain"

    elif code in [71, 73, 75, 85, 86]:
        return "Snow"

    elif code in [95, 96, 99]:
        return "Storm"

    else:
        return "Unknown"

def get_weather(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True
        }

        response = requests.get(url, params=params).json()
        weather = response["current_weather"]

        temperature = weather["temperature"]
        windspeed = weather["windspeed"]
        code = weather["weathercode"]

        # convert weather code → readable text
        desc = get_weather_desc(code)

        return temperature, desc
    except:
        return 15.0, "Cloudy"  # fallback
    
# 🔹 NEW: get real traffic speed
def get_traffic_speed(lat, lon):
    try:
        url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
        params = {
            "point": f"{lat},{lon}",
            "key": TOMTOM_KEY
        }

        r = requests.get(url, params=params).json()

        return r["flowSegmentData"]["currentSpeed"]

    except:
        return random.randint(20, 50)  # fallback


# 🔹 NEW: realistic parking estimation
def estimate_parking(speed, hour, base_level, weather_desc):

    # rush hour
    if 7 <= hour <= 10 or 16 <= hour <= 19:
        base_level -= 15

    # traffic effect
    congestion = max(0, (40 - speed))
    base_level -= congestion * 0.5

    # 🌧️ weather effect
    if weather_desc in ["Storm", "Snow"]:
        base_level -= 15   # more cars → fewer spaces
    if weather_desc == "Rain":
        base_level -= 10
    elif weather_desc == "Clear":
        base_level += 5    # nicer weather → less congestion

    # noise
    base_level += random.randint(-5, 5)

    return int(max(0, min(100, base_level)))

def collect_data():
    init_db()
    print("🚀 Ο συλλέκτης ξεκίνησε...")
    while True:
        try:
            # Parking Data
            p_url = f"https://api.tfl.gov.uk/Place/Type/CarPark?app_key={TFL_KEY}"
            parking_list = requests.get(p_url).json()

            conn = sqlite3.connect('london_smart_parking.db')
            cursor = conn.cursor()

            # Παίρνουμε τους πρώτους 30 σταθμούς για να έχουμε πολλές περιοχές
            for park in parking_list[:30]:
                name = park['commonName']
                lat, lon = park['lat'], park['lon']
                speed = get_traffic_speed(lat, lon)
                base = 60 - (hash(name) % 30) # give each parking personality
                now = datetime.now().strftime("%H:%M:%S")
                temperature, weather_desc = get_weather(lat, lon)
                free = estimate_parking(speed, hour, base, weather_desc)
                
                cursor.execute("INSERT INTO parking_logs (timestamp, parking_name, free_spaces, traffic_speed, temperature, weather_desc, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (now, name, free, speed, temperature, weather_desc, lat, lon))
            
            conn.commit()
            conn.close()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Καταγράφηκαν 30 σταθμοί.")
            time.sleep(60) # Ενημέρωση κάθε 1 λεπτό

        except Exception as e:
            print(f"❌ Σφάλμα: {e}")
            time.sleep(10)

if __name__ == "__main__":
    collect_data()