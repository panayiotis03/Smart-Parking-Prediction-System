import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

# 1. Ρυθμίσεις Σελίδας
st.set_page_config(page_title="DataVision - Smart Parking", layout="wide")

# 2. Συντεταγμένες για κάθε Περιοχή
view_centers = {
    "Κέντρο Λεμεσού": {"lat": 34.6748, "lon": 33.0448, "zoom": 16},
    "Παλιό Λιμάνι / Μαρίνα": {"lat": 34.6710, "lon": 33.0400, "zoom": 16},
    "Οδός Ανεξαρτησίας": {"lat": 34.6765, "lon": 33.0425, "zoom": 17}
}

# 3. Sidebar - Configurations
with st.sidebar:
    st.header("🛠️ Configurations")
    selected_zone = st.selectbox(
        "Επιλογή Ζώνης Ελέγχου:",
        list(view_centers.keys())
    )
    prediction_time = st.select_slider(
        "Ορίζοντας Πρόβλεψης (λεπτά):",
        options=[15, 30, 45, 60], value=30
    )

# 4. Δεδομένα Parking 
parking_data = pd.DataFrame({
    'lat': [34.6748, 34.6735, 34.6762], 
    'lon': [33.0448, 33.0405, 33.0415], 
    'name': ['Μώλος 1', 'Παλιό Λιμάνι', 'Ανεξαρτησίας'],
    'color': [[0, 255, 0, 160], [255, 165, 0, 160], [255, 0, 0, 160]],
    'radius': [50, 50, 40] 
})

# 5. Main Panel
st.title("🅿️ DataVision: Predictive Map")

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader(f"📍 Εστίαση: {selected_zone}")
    
    # View State βάσει της επιλογής στο Sidebar
    new_view = pdk.ViewState(
        latitude=view_centers[selected_zone]["lat"],
        longitude=view_centers[selected_zone]["lon"],
        zoom=view_centers[selected_zone]["zoom"],
        pitch=0
    )
    
    st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/light-v9',
        initial_view_state=new_view,
        layers=[
            pdk.Layer(
                'ScatterplotLayer',
                parking_data,
                get_position='[lon, lat]',
                get_fill_color='color',
                get_radius='radius',
                pickable=True,
            ),
        ],
    ))

with col2:
    st.subheader("📊 Analytics")
    prob = int(max(10, 90 - (prediction_time * 0.8)))
    st.metric("Πιθανότητα Εύρεσης", f"{prob}%")
    st.line_chart(np.random.randint(40, 90, size=(10, 1)))
