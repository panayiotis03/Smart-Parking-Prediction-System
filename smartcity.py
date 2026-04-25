import requests
import sqlite3
import time
from datetime import datetime
import random

TFL_KEY = "dad0400bba354bdea4898dabf6167f22"
TOMTOM_KEY = "K6LFXx456fgf2nWMmEJqx75Fl9h3CTXh"
WEATHER_KEY = "NA22UXZL3HRV6LJUVVWBTJCZK"

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
                speed = random.randint(15, 55) # Live προσομοίωση ταχύτητας
                free = random.randint(5, 80)
                now = datetime.now().strftime("%H:%M:%S")
                
                cursor.execute("INSERT INTO parking_logs (timestamp, parking_name, free_spaces, traffic_speed, temperature, weather_desc, lat, lon) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                               (now, name, free, speed, 15.0, "Cloudy", lat, lon))
            
            conn.commit()
            conn.close()
            print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] Καταγράφηκαν 30 σταθμοί.")
            time.sleep(60) # Ενημέρωση κάθε 1 λεπτό

        except Exception as e:
            print(f"❌ Σφάλμα: {e}")
            time.sleep(10)

if __name__ == "__main__":
    collect_data()