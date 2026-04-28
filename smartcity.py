import requests
import sqlite3
import time
from datetime import datetime

TFL_KEY     = "dad0400bba354bdea4898dabf6167f22"
TOMTOM_KEY  = "K6LFXx456fgf2nWMmEJqx75Fl9h3CTXh"
WEATHER_KEY = "NA22UXZL3HRV6LJUVVWBTJCZK"

COLLECT_INTERVAL_SEC = 60
WEATHER_CACHE_SEC    = 600
TOMTOM_DELAY_SEC     = 0.3

def init_db():
    with sqlite3.connect('london_smart_parking.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS parking_logs (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT,
                parking_name  TEXT,
                free_spaces   INTEGER,
                traffic_speed REAL,
                temperature   REAL,
                weather_desc  TEXT,
                lat           REAL,
                lon           REAL
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_parking_name_id
            ON parking_logs (parking_name, id DESC)
        ''')
    print("✅ Βάση δεδομένων έτοιμη.")

def get_parking_data():
    """
    TfL CarPark API:
    - NumberOfSpaces = συνολικές θέσεις (static, από props)
    - Occupancy από /Occupancy/CarPark/{id} (httpStatusCode 500 = δεν υποστηρίζεται)
    - Fallback: χρησιμοποιούμε το Bay occupancy μέσω του OccupancyUrl αν υπάρχει,
      αλλιώς simulation βάσει ώρας + NumberOfSpaces 
    """
    url  = f"https://api.tfl.gov.uk/Place/Type/CarPark?app_key={TFL_KEY}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    parks = resp.json()

    result = []
    now_hour = datetime.now().hour

    for park in parks[:30]:
        name    = park.get('commonName', 'Unknown')
        lat     = park.get('lat', 0)
        lon     = park.get('lon', 0)
        park_id = park.get('id', '')
        props   = {x['key']: x['value'] for x in park.get('additionalProperties', [])}

        # Συνολικές θέσεις από props
        try:
            total_spaces = int(props.get('NumberOfSpaces', 50))
        except (ValueError, TypeError):
            total_spaces = 50

        free_spaces = None

        # Προσπάθεια 1: TfL Occupancy API 
        try:
            occ_url  = f"https://api.tfl.gov.uk/Occupancy/CarPark/{park_id}?app_key={TFL_KEY}"
            occ_resp = requests.get(occ_url, timeout=8)
            if occ_resp.status_code == 200:
                data = occ_resp.json()
                bays = data.get('bays', [])
                if bays:
                    free_spaces = sum(b.get('free', 0) for b in bays)
                    print(f"  ✅ Live occupancy: {name} → {free_spaces} free")
        except Exception:
            pass

        # Προσπάθεια 2: Ρεαλιστικό pattern βάσει ώρας + total_spaces
        # (Χρησιμοποιείται ΜΟΝΟ αν το TfL δεν δίνει live data)
        # Pattern: πρωί αιχμής (8-10) γεμάτο, βράδυ άδειο
        if free_spaces is None:
            import math
            # Occupancy: peak στις 9-10 πρωί και 5-6 το απόγευμα
            morning_peak = math.exp(-0.5 * ((now_hour - 9) / 2.0) ** 2)
            evening_peak = math.exp(-0.5 * ((now_hour - 17) / 2.0) ** 2)
            occupancy_rate = 0.3 + 0.6 * max(morning_peak, evening_peak)
            occupancy_rate = min(0.95, max(0.05, occupancy_rate))
            # Μικρή διαφοροποίηση ανά parking (βάσει ID hash)
            variation = (hash(park_id) % 20 - 10) / 100.0
            occupancy_rate = min(0.98, max(0.02, occupancy_rate + variation))
            free_spaces = max(0, int(total_spaces * (1 - occupancy_rate)))
            print(f"  📊 Pattern-based: {name} → {free_spaces}/{total_spaces} free ({int(occupancy_rate*100)}% full)")

        result.append({
            'name': name, 'lat': lat, 'lon': lon,
            'free_spaces': free_spaces, 'total_spaces': total_spaces
        })

    return result

def get_traffic_speed(lat, lon):
    url = (
        f"https://api.tomtom.com/traffic/services/4/flowSegmentData/"
        f"absolute/10/json?point={lat},{lon}&unit=KMPH&key={TOMTOM_KEY}"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json().get('flowSegmentData', {}).get('currentSpeed', None)

_weather_cache = {'data': None, 'ts': 0}

def get_weather():
    now = time.time()
    if _weather_cache['data'] and (now - _weather_cache['ts']) < WEATHER_CACHE_SEC:
        return _weather_cache['data']
    url = (
        f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/"
        f"timeline/London,UK/today?unitGroup=metric&include=current"
        f"&key={WEATHER_KEY}&contentType=json"
    )
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    current = resp.json().get('currentConditions', {})
    result  = {
        'temperature':  current.get('temp', 15.0),
        'weather_desc': current.get('conditions', 'Unknown')
    }
    _weather_cache.update({'data': result, 'ts': now})
    print(f"  🌤️  Καιρός: {result['temperature']}°C, {result['weather_desc']}")
    return result

def collect_once(temp, desc, parking_data, now_ts):
    """
    Παράλληλη συλλογή traffic με threading.
    Όλα τα TomTom calls τρέχουν ταυτόχρονα → μεταξύ 3-5 δευτερόλεπτα για 30 parkings περίπου.
    Μετά ένα bulk insert → όλα εμφανίζονται ταυτοχρονα στο UI.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def fetch_park(park):
        try:
            speed = get_traffic_speed(park['lat'], park['lon'])
            if speed is not None:
                return (now_ts, park['name'], park['free_spaces'],
                        speed, temp, desc, park['lat'], park['lon'])
        except Exception as e:
            print(f"  ⚠️ TomTom error ({park['name']}): {e}")
        return None

    print(f"  🚗 Παράλληλη συλλογή traffic για {len(parking_data)} parking...")
    rows = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_park, p): p for p in parking_data}
        for future in as_completed(futures):
            result = future.result()
            if result:
                rows.append(result)

    if rows:
        with sqlite3.connect('london_smart_parking.db') as conn:
            conn.executemany(
                """INSERT INTO parking_logs
                   (timestamp, parking_name, free_spaces, traffic_speed,
                    temperature, weather_desc, lat, lon)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows
            )
        print(f"  💾 Bulk insert: {len(rows)} parking ταυτόχρονα ✅")

    return len(rows), len(parking_data) - len(rows)


def collect_data():
    init_db()
    print(" Collector ξεκίνησε — πρώτα δεδομένα σε ~30 δευτερόλεπτα")
    print("-" * 55)

    while True:
        cycle_start = time.time()
        try:
            # Καιρός
            try:
                weather = get_weather()
                temp, desc = weather['temperature'], weather['weather_desc']
            except Exception as e:
                print(f"⚠️  Weather error: {e} — χρησιμοποιώ default")
                temp, desc = 15.0, "Cloudy"

            # Parking
            try:
                parking_data = get_parking_data()
                print(f"🅿️  {len(parking_data)} parking — ξεκινώ αποθήκευση...")
            except Exception as e:
                print(f"❌ TfL error: {e}")
                time.sleep(30)
                continue

            now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            saved, skipped = collect_once(temp, desc, parking_data, now_ts)

            elapsed = time.time() - cycle_start
            print(f"✅ [{now_ts}] Saved: {saved} | Skipped: {skipped} | {elapsed:.0f}s")
            sleep_time = max(5, COLLECT_INTERVAL_SEC - elapsed)
            print(f"⏳ Επόμενο update σε {sleep_time:.0f}s...")
            time.sleep(sleep_time)

        except Exception as e:
            print(f"❌ Σφάλμα: {e}")
            time.sleep(30)

if __name__ == "__main__":
    collect_data()
