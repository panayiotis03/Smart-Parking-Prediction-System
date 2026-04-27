import streamlit as st
import sqlite3
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_autorefresh import st_autorefresh

# Ρύθμιση σελίδας
st.set_page_config(page_title="London Smart Parking Pro", layout="wide")

st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container { padding: 0.5rem 0.5rem !important; }
}
</style>
""", unsafe_allow_html=True)

# Ανανέωση κάθε 20 δευτερόλεπτα για live αίσθηση
st_autorefresh(interval=20 * 1000, key="datarefresh")

# Auto-detect mobile μέσω JS + query params (αξιόπιστη μέθοδος για Streamlit)
import streamlit.components.v1 as components

# Auto-detect mobile: διαβάζουμε το query param που γράφει ο browser
import streamlit.components.v1 as components

# Το JS τρέχει στον browser, γράφει ?mobile=1 ή ?mobile=0 στο URL
# χρησιμοποιώντας το Streamlit's setQueryParam μέσω postMessage
components.html("""
<script>
(function() {
    const isMobile = window.innerWidth < 768 ? '1' : '0';
    const url = new URL(window.parent.location.href);
    if (url.searchParams.get('mobile') !== isMobile) {
        url.searchParams.set('mobile', isMobile);
        window.parent.history.replaceState({}, '', url.toString());
        window.parent.location.reload();
    }
})();
</script>
""", height=0)

qp = st.query_params
is_mobile = qp.get("mobile", "0") == "1"

if 'selected_parking' not in st.session_state:
    st.session_state.selected_parking = None

# ---ΣΥΝΑΡΤΗΣΕΙΣ ---
def get_thresholds(df_spaces):
    """
    Δυναμικά όρια βάσει percentiles:
    - Πράσινο: top 33% (πάνω από το 67ο percentile)
    - Πορτοκαλί: μεσαίο 33% (34ο–66ο percentile)
    - Κόκκινο: κάτω 33% (κάτω από το 34ο percentile)
    Εγγυάται ότι πάντα υπάρχουν και τα 3 χρώματα.
    """
    p67 = int(df_spaces.quantile(0.67))
    p33 = int(df_spaces.quantile(0.33))
    # Αποφυγή ίσων ορίων
    if p67 == p33:
        p67 = p33 + 1
    return p67, p33   # green_thr, orange_thr

def get_status(free_spaces_abs, green_thr, orange_thr):
    """Επιστρέφει (χρώμα, label, τύπος) βάσει percentile ορίων."""
    if free_spaces_abs >= green_thr:
        return "#28a745", "🟢 Αρκετή διαθεσιμότητα", "success"
    elif free_spaces_abs >= orange_thr:
        return "#fd7e14", "🟠 Μέτρια Επιλογή", "warning"
    else:
        return "#dc3545", "🔴 Σχεδόν καμία διαθεσιμότητα", "error"

def render_status_box(status_type, label):
    if status_type == "success":
        st.success(label)
    elif status_type == "warning":
        st.warning(label)
    else:
        st.error(label)

def render_analytics(df, current_horizon):
    """Κοινό analytics panel για mobile & desktop."""
    MAX_SPACES = max(df['free_spaces'].max(), 1)
    green_thr, orange_thr = get_thresholds(df['free_spaces'])

    if not st.session_state.selected_parking:
        st.warning("👈 Πατήστε σε έναν κύκλο στον χάρτη.")
        st.write("---")
        st.write("**🏆 Κορυφαία Parking τώρα:**")
        top_3 = df.sort_values(by='free_spaces', ascending=False).head(3)
        for _, r in top_3.iterrows():
            _, lbl, _ = get_status(r['free_spaces'], green_thr, orange_thr)
            st.markdown(f"{lbl.split()[0]} **{r['parking_name']}** — {r['free_spaces']} θέσεις")
        return

    selected_data = df[df['parking_name'] == st.session_state.selected_parking]
    if selected_data.empty:
        return

    row = selected_data.iloc[0]

    # --- Live τιμές (από APIs τώρα) ---
    live_spaces  = row['free_spaces']
    live_speed   = row['traffic_speed']
    live_temp    = row['temperature']
    live_weather = row['weather_desc']

    # --- Προβλεπόμενες τιμές (πραγματικά δεδομένα από DB offset) ---
    pred_spaces  = int(row['pred_free_spaces'])  if pd.notna(row.get('pred_free_spaces'))  else live_spaces
    pred_speed   = int(row['pred_traffic_speed']) if pd.notna(row.get('pred_traffic_speed')) else live_speed
    pred_temp    = row.get('pred_temperature', live_temp)
    pred_weather = row.get('pred_weather_desc', live_weather)

    # Πιθανότητα εύρεσης — άμεσα συνδεδεμένη με τη σήμανση
    # 🟢 Αρκετή  → 65–95%
    # 🟠 Μέτρια  → 30–64%
    # 🔴 Σχεδόν καμία → 0–29%
    def spaces_to_reliability(spaces, speed, g_thr, o_thr):
        speed_bonus = min((speed / 60.0) * 10, 10)  # max +10% από κίνηση
        if spaces >= g_thr:
            # Πράσινο: 65–95, ανάλογα πόσο πάνω από το όριο
            base = 65 + min(30, int((spaces - g_thr) / max(g_thr, 1) * 30))
        elif spaces >= o_thr:
            # Πορτοκαλί: 30–64
            base = 30 + int((spaces - o_thr) / max(g_thr - o_thr, 1) * 34)
        else:
            # Κόκκινο: 0–29
            base = int((spaces / max(o_thr, 1)) * 29)
        return max(0, min(100, int(base + speed_bonus)))

    live_rel   = spaces_to_reliability(live_spaces,  live_speed,  green_thr, orange_thr)
    future_rel = spaces_to_reliability(pred_spaces,  pred_speed,  green_thr, orange_thr)

    # Σήμανση βάσει live ή πρόβλεψης
    display_spaces = pred_spaces if current_horizon > 0 else live_spaces
    display_speed  = pred_speed  if current_horizon > 0 else live_speed
    display_temp   = pred_temp   if current_horizon > 0 else live_temp
    display_weather= pred_weather if current_horizon > 0 else live_weather
    _, status_label, status_type = get_status(display_spaces, green_thr, orange_thr)

    st.markdown(f"### 🅿️ {st.session_state.selected_parking}")

    m_col1, m_col2 = st.columns([1, 1])
    with m_col1:
        if current_horizon == 0:
            st.metric("Ελεύθερες Θέσεις (Live)", f"{live_spaces}")
            st.metric("Πιθανότητα Εύρεσης",       f"{live_rel}%")
        else:
            st.metric(
                f"Πρόβλεψη σε {current_horizon}'",
                f"{pred_spaces} θέσεις",
                delta=int(pred_spaces - live_spaces)
            )
            st.metric(
                f"Πιθανότητα σε {current_horizon}'",
                f"{future_rel}%",
                delta=f"{int(future_rel - live_rel)}%"
            )
    with m_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        render_status_box(status_type, status_label)

    # Γράφημα τάσης: ομαλή προβολή βάσει trend (χωρίς DB calls per step)
    if current_horizon > 0:
        st.divider()
        st.write(f"📈 **Τάση Διαθεσιμότητας & Κίνησης (επόμενα {current_horizon} λεπτά)**")

        fs_delta = float(row.get('fs_delta_per_min', 0))
        ts_delta = float(row.get('ts_delta_per_min', 0))
        max_fs_ch = live_spaces * 0.40
        max_ts_ch = live_speed  * 0.35

        steps = list(range(0, current_horizon + 1, max(1, current_horizon // 8)))
        chart_rows = []
        for s in steps:
            fs = live_spaces + fs_delta * s
            fs = max(max(0, live_spaces - max_fs_ch), min(live_spaces + max_fs_ch, fs))
            ts = live_speed  + ts_delta * s
            ts = max(max(0, live_speed  - max_ts_ch), min(live_speed  + max_ts_ch, ts))
            chart_rows.append({
                "Χρόνος":        f"+{s}'" if s > 0 else "Τώρα",
                "Θέσεις":        max(0, int(round(fs))),
                "Κίνηση (km/h)": max(0, int(round(ts))),
            })

        chart_df = pd.DataFrame(chart_rows).set_index("Χρόνος")
        tab1, tab2 = st.tabs(["🅿️ Θέσεις", "🚗 Κίνηση"])
        with tab1:
            st.area_chart(chart_df[["Θέσεις"]], color="#29b5e8")
        with tab2:
            st.area_chart(chart_df[["Κίνηση (km/h)"]], color="#fd7e14")

    st.divider()
    mc1, mc2 = st.columns(2)
    mc1.metric("Θέσεις Τώρα", live_spaces)
    mc2.metric(
        "Κίνηση",
        f"{int(display_speed)} km/h",
        delta=f"{int(display_speed - live_speed)} km/h" if current_horizon > 0 else None
    )

    st.write("**Πληρότητα:**")
    st.progress(max(0.0, min(1.0, 1.0 - display_spaces / MAX_SPACES)))
    st.write(f"🌡️ {display_temp}°C | {display_weather}")
    wait_val = "0-3" if display_spaces >= green_thr else ("5-10" if display_spaces >= orange_thr else "10-15")
    st.info(f"⏱️ Εκτ. χρόνος εύρεσης: **{wait_val}'**")


def build_map(df, zoom, width, height, key):
    """Φτιάχνει τον folium χάρτη και τον εμφανίζει."""
    green_thr, orange_thr = get_thresholds(df['free_spaces'])
    m = folium.Map(location=[51.5074, -0.1278], zoom_start=zoom, tiles="cartodbpositron")
    for _, row in df.iterrows():
        color, status_label, _ = get_status(row['free_spaces'], green_thr, orange_thr)
        tooltip_html = (
            f"<b>{row['parking_name']}</b><br>"
            f"{status_label}<br>"
            f"Ελεύθερες θέσεις: {row['free_spaces']}"
        )
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=10 if width == "100%" else 12,
            color=color, fill=True, fill_color=color, fill_opacity=0.85,
            tooltip=folium.Tooltip(tooltip_html, sticky=True),
            popup=row['parking_name']
        ).add_to(m)
    return st_folium(m, width=width, height=height, key=key), green_thr, orange_thr

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛠️ Smart Control")

    st.divider()
    zone_filter = st.selectbox("Περιοχή Ελέγχου:", ["Όλο το Λονδίνο", "Κέντρο", "Ημικέντρο", "Περίχωρα"])

    st.divider()
    mode = st.radio("Λειτουργία Προβολής:", ["🔴 Live Τώρα", "🔮 Πρόβλεψη"])
    current_horizon = st.slider("Ορίζοντας Πρόβλεψης (λεπτά):", 5, 60, 30) if "Πρόβλεψη" in mode else 0

    st.divider()
    if st.button("Καθαρισμός Επιλογής 🔄"):
        st.session_state.selected_parking = None
        st.rerun()

# --- ΔΕΔΟΜΕΝΑ ---
try:
    query_live = """
    SELECT parking_name, lat, lon,
           ROUND(AVG(free_spaces))   as free_spaces,
           ROUND(AVG(traffic_speed)) as traffic_speed,
           MAX(temperature)          as temperature,
           MAX(weather_desc)         as weather_desc
    FROM (
        SELECT p.parking_name, p.lat, p.lon,
               p.free_spaces, p.traffic_speed,
               p.temperature, p.weather_desc,
               ROW_NUMBER() OVER (
                   PARTITION BY p.parking_name
                   ORDER BY p.id DESC
               ) as rn
        FROM parking_logs p
    )
    WHERE rn <= 10
    GROUP BY parking_name
    """

    query_trend = """
    SELECT parking_name,
           ROUND(AVG(CASE WHEN rn <= 10 THEN free_spaces   END)) as fs_recent,
           ROUND(AVG(CASE WHEN rn >= 50 AND rn <= 60 THEN free_spaces   END)) as fs_older,
           ROUND(AVG(CASE WHEN rn <= 10 THEN traffic_speed END)) as ts_recent,
           ROUND(AVG(CASE WHEN rn >= 50 AND rn <= 60 THEN traffic_speed END)) as ts_older,
           COUNT(*) as total_rows
    FROM (
        SELECT p.parking_name, p.free_spaces, p.traffic_speed,
               ROW_NUMBER() OVER (
                   PARTITION BY p.parking_name
                   ORDER BY p.id DESC
               ) as rn
        FROM parking_logs p
    )
    WHERE rn <= 60
    GROUP BY parking_name
    """

    with sqlite3.connect('london_smart_parking.db') as conn:
        df_live  = pd.read_sql_query(query_live,  conn)
        df_trend = pd.read_sql_query(query_trend, conn)

    # ── Άδεια βάση: ο collector δεν έχει γράψει δεδομένα ακόμα ──
    if df_live.empty:
        st.info("⏳ Αναμονή δεδομένων από τον collector...")
        st.markdown("""
        **Η βάση είναι άδεια.** Βεβαιώσου ότι ο collector τρέχει:
        ```bash
        python collector.py
        ```
        Το UI θα ανανεωθεί αυτόματα σε 20 δευτερόλεπτα.
        """)
        st.stop()

    df_live['free_spaces']   = df_live['free_spaces'].fillna(0).astype(int)
    df_live['traffic_speed'] = df_live['traffic_speed'].fillna(0).astype(int)

    # Trend: αλλαγή σε 50 λεπτά → κανονικοποίηση σε ανά λεπτό
    # Αν δεν υπάρχουν αρκετά δεδομένα (< 20 rows), trend = 0
    df_trend['has_history'] = df_trend['total_rows'] >= 20
    df_trend['fs_delta_per_min'] = (
        (df_trend['fs_recent'] - df_trend['fs_older']) / 50.0
    ).where(df_trend['has_history'], other=0).fillna(0)
    df_trend['ts_delta_per_min'] = (
        (df_trend['ts_recent'] - df_trend['ts_older']) / 50.0
    ).where(df_trend['has_history'], other=0).fillna(0)

    # Merge live + trend
    df = df_live.merge(
        df_trend[['parking_name', 'fs_delta_per_min', 'ts_delta_per_min']],
        on='parking_name', how='left'
    )
    df['fs_delta_per_min'] = df['fs_delta_per_min'].fillna(0)
    df['ts_delta_per_min'] = df['ts_delta_per_min'].fillna(0)

    # Πρόβλεψη = live + (trend_per_min × horizon_λεπτά)
    # Hard clamp: max ±40% από live τιμή (ρεαλισμός)
    if current_horizon > 0:
        raw_pred_fs = df['free_spaces'] + df['fs_delta_per_min'] * current_horizon
        max_change_fs = df['free_spaces'] * 0.40
        df['pred_free_spaces'] = raw_pred_fs.clip(
            lower=(df['free_spaces'] - max_change_fs).clip(lower=0),
            upper=(df['free_spaces'] + max_change_fs)
        ).round().astype(int)

        raw_pred_ts = df['traffic_speed'] + df['ts_delta_per_min'] * current_horizon
        max_change_ts = df['traffic_speed'] * 0.35
        df['pred_traffic_speed'] = raw_pred_ts.clip(
            lower=(df['traffic_speed'] - max_change_ts).clip(lower=0),
            upper=(df['traffic_speed'] + max_change_ts)
        ).round().astype(int)
    else:
        df['pred_free_spaces']   = df['free_spaces']
        df['pred_traffic_speed'] = df['traffic_speed']

    df['pred_temperature']  = df['temperature']
    df['pred_weather_desc'] = df['weather_desc']

    # ============================================================
    # ΦΙΛΤΡΑΡΙΣΜΑ ΠΕΡΙΟΧΗΣ — βάσει απόστασης από κέντρο Λονδίνου
    # Κέντρο Λονδίνου (Charing Cross): 51.5074, -0.1278
    # Υπολογίζουμε απόσταση Euclidean και χωρίζουμε σε ζώνες
    # ============================================================
    LONDON_LAT, LONDON_LON = 51.5074, -0.1278

    df['dist_km'] = (
        ((df['lat'] - LONDON_LAT) * 111.0) ** 2 +
        ((df['lon'] - LONDON_LON) * 111.0 * 0.64) ** 2
    ) ** 0.5

    # Δυναμικά όρια βάσει των πραγματικών δεδομένων (percentiles)
    p33 = df['dist_km'].quantile(0.40)  # κοντύτερα 40% = Κέντρο
    p66 = df['dist_km'].quantile(0.75)  # 40-75% = Ημικέντρο, >75% = Περίχωρα

    if zone_filter == "Κέντρο":
        df = df[df['dist_km'] <= p33]
    elif zone_filter == "Ημικέντρο":
        df = df[(df['dist_km'] > p33) & (df['dist_km'] <= p66)]
    elif zone_filter == "Περίχωρα":
        df = df[df['dist_km'] > p66]

    if df.empty:
        st.error(f"Δεν βρέθηκαν parking για '{zone_filter}'.")
        with st.expander("🔍 Debug — Κατανομή αποστάσεων"):
            with sqlite3.connect('london_smart_parking.db') as conn_d:
                df_all = pd.read_sql_query(
                    "SELECT parking_name, lat, lon FROM parking_logs GROUP BY parking_name",
                    conn_d
                )
            df_all['dist_km'] = (
                ((df_all['lat'] - LONDON_LAT) * 111.0) ** 2 +
                ((df_all['lon'] - LONDON_LON) * 111.0 * 0.64) ** 2
            ) ** 0.5
            st.write(f"Κέντρο: ≤{p33:.1f} km | Ημικέντρο: {p33:.1f}–{p66:.1f} km | Περίχωρα: >{p66:.1f} km")
            st.dataframe(df_all[['parking_name','dist_km']].sort_values('dist_km').round(2))
    else:

        # ============================================================
        # MOBILE LAYOUT — Tabs: Χάρτης | Analytics
        # ============================================================
        if is_mobile:
            st.markdown(f"### 📍 {zone_filter}")
            tab_map, tab_analytics = st.tabs(["🗺️ Χάρτης", "📊 Analytics"])

            with tab_map:
                map_data, green_thr, orange_thr = build_map(
                    df, zoom=10, width="100%", height=450, key="main_map"
                )
                legend = (f"🟢 **≥{green_thr}** &nbsp; "
                          f"🟠 **{orange_thr}–{green_thr-1}** &nbsp; "
                          f"🔴 **<{orange_thr} θέσεις**")
                st.markdown(legend, unsafe_allow_html=True)

                if map_data and map_data.get("last_object_clicked"):
                    clat = map_data["last_object_clicked"]["lat"]
                    clng = map_data["last_object_clicked"]["lng"]
                    match = df[(abs(df['lat'] - clat) < 0.001) & (abs(df['lon'] - clng) < 0.001)]
                    if not match.empty:
                        st.session_state.selected_parking = match.iloc[0]['parking_name']
                        st.success(f"✅ Επιλέχθηκε: **{st.session_state.selected_parking}** — Πήγαινε στο tab 📊 Analytics")

            with tab_analytics:
                render_analytics(df, current_horizon)

        # ============================================================
        # DESKTOP LAYOUT
        # ============================================================
        else:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader(f"📍 Χάρτης: {zone_filter}")
                map_data, green_thr, orange_thr = build_map(df, zoom=11, width=1080, height=850, key="main_map")
                legend = f"🟢 **≥{green_thr} θέσεις** &nbsp; 🟠 **{orange_thr}–{green_thr-1}** &nbsp; 🔴 **<{orange_thr} θέσεις**"
                st.markdown(legend, unsafe_allow_html=True)

                if map_data and map_data.get("last_object_clicked"):
                    clat = map_data["last_object_clicked"]["lat"]
                    clng = map_data["last_object_clicked"]["lng"]
                    match = df[(abs(df['lat'] - clat) < 0.001) & (abs(df['lon'] - clng) < 0.001)]
                    if not match.empty:
                        st.session_state.selected_parking = match.iloc[0]['parking_name']

            with col2:
                st.subheader("📊 Smart Analytics")
                render_analytics(df, current_horizon)

except Exception as e:
    st.error(f"⚠️ Σφάλμα: {e}")
    st.markdown("""
    **Πιθανές αιτίες:**
    - Ο collector δεν τρέχει (`python collector.py`)
    - Η βάση `london_smart_parking.db` δεν βρίσκεται στον ίδιο φάκελο
    - Πρόβλημα σύνδεσης με τα APIs
    """)
    import traceback
    with st.expander("🔍 Τεχνικές λεπτομέρειες"):
        st.code(traceback.format_exc())
