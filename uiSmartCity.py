import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh
import random

# Ρύθμιση σελίδας
st.set_page_config(page_title="London Smart Parking Pro", layout="wide")

# Ανανέωση κάθε 20 δευτερόλεπτα
st_autorefresh(interval=20 * 1000, key="datarefresh")

# Αρχικοποίηση session state
if 'selected_parking' not in st.session_state:
    st.session_state.selected_parking = None

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛠️ Smart Control")
    zone_filter = st.selectbox("Περιοχή Ελέγχου:", ["Όλο το Λονδίνο", "Κέντρο", "Περίχωρα"])
    
    st.divider()
    mode = st.radio("Λειτουργία Προβολής:", ["🔴 Live Τώρα", "🔮 Πρόβλεψη"])
    
    if "Πρόβλεψη" in mode:
        current_horizon = st.slider("Ορίζοντας Πρόβλεψης (λεπτά):", 5, 60, 30, key="prediction_slider")
    else:
        current_horizon = 0
    
    st.divider()
    if st.button("Καθαρισμός Επιλογής 🔄"):
        st.session_state.selected_parking = None
        st.rerun()

# --- ΑΝΑΓΝΩΣΗ ΔΕΔΟΜΕΝΩΝ ---
try:
    conn = sqlite3.connect('london_smart_parking.db')
    
    query = """
    SELECT 
        parking_name, 
        lat, 
        lon, 
        AVG(free_spaces) as free_spaces, 
        AVG(traffic_speed) as traffic_speed, 
        MAX(temperature) as temperature, 
        MAX(weather_desc) as weather_desc
    FROM (
        SELECT * FROM parking_logs 
        ORDER BY id DESC 
        LIMIT 600 
    )
    GROUP BY parking_name
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    df['free_spaces'] = df['free_spaces'].round().astype(int)
    df['traffic_speed'] = df['traffic_speed'].round().astype(int)

    # --- ΦΙΛΤΡΑΡΙΣΜΑ ΠΕΡΙΟΧΗΣ ---
    if zone_filter == "Κέντρο":
        df = df[(df['lat'] > 51.48) & (df['lat'] < 51.53) & (df['lon'] > -0.15) & (df['lon'] < -0.05)]
    elif zone_filter == "Περίχωρα":
        df = df[(df['lat'] <= 51.48) | (df['lat'] >= 51.53)]

    if not df.empty:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader(f"📍 Χάρτης: {zone_filter}")
            m = folium.Map(location=[51.5074, -0.1278], zoom_start=11, tiles="cartodbpositron")
            
            # Χρωματική κωδικοποίηση βάσει % ελεύθερων θέσεων
            def get_status(free_pct):
                if free_pct >= 55:
                    return "#28a745", "🟢 Αρκετή διαθεσιμότητα"
                elif free_pct >= 40:
                    return "#fd7e14", "🟠 Μέτρια Επιλογή"
                else:
                    return "#dc3545", "🔴 Σχεδόν καμία διαθεσιμότητα"

            for _, row in df.iterrows():
                free_pct = row['free_spaces']  # 0 = γεμάτο, 100 = άδειο
                color, status_label = get_status(free_pct)
                
                tooltip_html = (
                    f"<b>{row['parking_name']}</b><br>"
                    f"{status_label}<br>"
                    f"Ελεύθερες θέσεις: {free_pct}% &nbsp;|&nbsp; Πληρότητα: {100 - free_pct}%"
                )

                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=12,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85,
                    tooltip=folium.Tooltip(tooltip_html, sticky=True),
                    popup=row['parking_name']
                ).add_to(m)

            map_data = st_folium(m, width=1080, height=850, key="main_map")
            
            if map_data and map_data.get("last_object_clicked"):
                clicked_lat = map_data["last_object_clicked"]["lat"]
                clicked_lon = map_data["last_object_clicked"]["lng"]
                match = df[(abs(df['lat'] - clicked_lat) < 0.001) & (abs(df['lon'] - clicked_lon) < 0.001)]
                if not match.empty:
                    st.session_state.selected_parking = match.iloc[0]['parking_name']

        with col2:
            st.subheader("📊 Smart Analytics")
            
            if st.session_state.selected_parking:
                selected_data = df[df['parking_name'] == st.session_state.selected_parking]
                
                if not selected_data.empty:
                    parking_data = selected_data.iloc[0]
                    
                    # ✅ FIX 2: Πολύ πιο εκφραστικοί υπολογισμοί για τον slider
                    #
                    # ΚΙΝΗΣΗ: Η κίνηση στο Λονδίνο επιδεινώνεται την ώρα αιχμής.
                    # Προσομοιώνουμε μείωση ταχύτητας κατά ~0.5 km/h ανά λεπτό
                    # αν η τρέχουσα ταχύτητα είναι χαμηλή (συμφόρηση),
                    # ή αύξηση αν είναι ήδη υψηλή (αποσυμφόρηση).
                    current_speed = parking_data['traffic_speed']
                    # Κανονικοποίηση: κάτω από 40 km/h = συμφόρηση, πάνω = ελεύθερο
                    congestion_factor = (40 - current_speed) / 40.0  # -1 έως +1
                    # Η κίνηση αλλάζει ±0.4 km/h ανά λεπτό ανάλογα με τη συμφόρηση
                    speed_change_per_min = congestion_factor * 0.4
                    future_traffic = current_speed + (speed_change_per_min * current_horizon)
                    future_traffic = max(5, min(90, future_traffic))

                    # ΘΕΣΕΙΣ: Αν η κίνηση επιδεινώνεται → λιγότερες θέσεις
                    # Κάθε 1 km/h μείωση ταχύτητας → -0.8 θέσεις
                    speed_delta = future_traffic - current_speed
                    spaces_change = speed_delta * 0.8  # Θετικό speed = περισσότερες θέσεις
                    pred_at_time = max(0, min(100, int(parking_data['free_spaces'] + spaces_change)))

                    # ΠΙΘΑΝΟΤΗΤΑ: Βασίζεται στις προβλεπόμενες θέσεις ΚΑΙ ταχύτητα
                    future_occupancy = 100 - pred_at_time
                    speed_weight = min(future_traffic / 60.0, 1.0)  # Υψηλή ταχύτητα = καλό
                    dynamic_reliability = max(0, min(100, int(
                        (pred_at_time * 0.6) +          # 60% βάρος στις θέσεις
                        (speed_weight * 100 * 0.4)       # 40% βάρος στην κίνηση
                    )))
                    
                    # Βοηθητική συνάρτηση σήμανσης (ίδια λογική με χάρτη)
                    def get_availability_status(free_pct):
                        if free_pct >= 55:
                            return "🟢", "Αρκετή διαθεσιμότητα", "success"
                        elif free_pct >= 40:
                            return "🟠", "Μέτρια Επιλογή", "warning"
                        else:
                            return "🔴", "Σχεδόν καμία διαθεσιμότητα", "error"

                    live_speed_weight = min(current_speed / 60.0, 1.0)
                    live_reliability = max(0, min(100, int(
                        (parking_data['free_spaces'] * 0.6) +
                        (live_speed_weight * 100 * 0.4)
                    )))

                    # Σήμανση βάσει live ή πρόβλεψης θέσεων
                    display_free = pred_at_time if current_horizon > 0 else parking_data['free_spaces']
                    dot, status_text, status_type = get_availability_status(display_free)

                    st.markdown(f"### Σταθμός: {st.session_state.selected_parking}")

                    # Μετρικές + σήμανση δίπλα-δίπλα
                    m_col1, m_col2 = st.columns([1, 1])

                    if current_horizon == 0:
                        with m_col1:
                            st.metric("Διαθέσιμες Θέσεις (Live)", f"{parking_data['free_spaces']}")
                            st.metric("Πιθανότητα Εύρεσης", f"{live_reliability}%")
                        with m_col2:
                            st.markdown(f"<br><br>", unsafe_allow_html=True)
                            if status_type == "success":
                                st.success(f"{dot} {status_text}")
                            elif status_type == "warning":
                                st.warning(f"{dot} {status_text}")
                            else:
                                st.error(f"{dot} {status_text}")
                    else:
                        with m_col1:
                            st.metric(f"Πρόβλεψη σε {current_horizon}'", f"{pred_at_time} θέσεις",
                                      delta=int(pred_at_time - parking_data['free_spaces']))
                            st.metric(f"Πιθανότητα σε {current_horizon}'", f"{dynamic_reliability}%",
                                      delta=f"{int(dynamic_reliability - live_reliability)}%")
                        with m_col2:
                            st.markdown(f"<br><br>", unsafe_allow_html=True)
                            if status_type == "success":
                                st.success(f"{dot} {status_text}")
                            elif status_type == "warning":
                                st.warning(f"{dot} {status_text}")
                            else:
                                st.error(f"{dot} {status_text}")

                    # ΓΡΑΦΗΜΑ
                    if current_horizon > 0:
                        st.divider()
                        st.write(f"📈 **Τάση Διαθεσιμότητας (επόμενα {current_horizon} λεπτά)**")
                        steps = list(range(0, current_horizon + 5, 5))
                        future_values = []
                        for s in steps:
                            ft = current_speed + (speed_change_per_min * s)
                            ft = max(5, min(90, ft))
                            sc = (ft - current_speed) * 0.8
                            fv = max(0, min(100, int(parking_data['free_spaces'] + sc)))
                            future_values.append(fv)
                        
                        pred_df = pd.DataFrame({
                            "Χρόνος": [f"+{s}'" if s > 0 else "Τώρα" for s in steps],
                            "Θέσεις": future_values
                        })
                        st.area_chart(pred_df.set_index("Χρόνος"), color="#29b5e8")

                    st.divider()
                    mc1, mc2 = st.columns(2)
                    mc1.metric("Θέσεις Τώρα", parking_data['free_spaces'])
                    display_traffic = future_traffic if current_horizon > 0 else current_speed
                    mc2.metric("Κίνηση", f"{int(display_traffic)} km/h",
                               delta=f"{int(display_traffic - current_speed)} km/h" if current_horizon > 0 else None)

                    st.write("**Πληρότητα:**")
                    current_occ_pct = (100 - pred_at_time) / 100.0 if current_horizon > 0 else (100 - parking_data['free_spaces']) / 100.0
                    st.progress(max(0.0, min(current_occ_pct, 1.0)))
                    
                    st.write(f"🌡️ {parking_data['temperature']}°C | {parking_data['weather_desc']}")
                    wait_val = "0-3" if (100 - pred_at_time) < 50 else "10-15"
                    st.info(f"⏱️ Εκτιμώμενος χρόνος εύρεσης: **{wait_val}'**")
            else:
                st.warning("👈 Επιλέξτε έναν σταθμό στο χάρτη.")
                st.write("---")
                st.write("**Κορυφαία Parking αυτή τη στιγμή:**")
                top_3 = df.sort_values(by='free_spaces', ascending=False).head(3)
                st.table(top_3[['parking_name', 'free_spaces']])
    else:
        st.error("Δεν βρέθηκαν δεδομένα στη βάση.")

except Exception as e:
    st.error(f"⚠️ Σφάλμα: {e}")