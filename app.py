import streamlit as st
import pandas as pd
import numpy as np
import pydeck as pdk

# 1. Ρυθμίσεις Σελίδας
st.set_page_config(page_title="DataVision - Smart Parking", layout="wide")

# 2. Συντεταγμένες και στατικά δεδομένα για κάθε περιοχή
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

# 4. Υπολογισμός Πιθανότητας και Χρώματος (Δυναμικά)
# Εδώ υπολογίζουμε την πιθανότητα (στο μέλλον θα έρχεται από το AI μοντέλο)
prob = int(max(10, 90 - (prediction_time * 0.8)))

# Λογική Χρωμάτων βάσει των ορίων σου:
# > 60% -> Κόκκινο | 35-60% -> Πορτοκαλί | < 35% -> Πράσινο
if prob > 60:
    current_color = [255, 0, 0, 160]    # ΚΟΚΚΙΝΟ (Δύσκολο Parking)
elif prob >= 35:
    current_color = [255, 165, 0, 160]  # ΠΟΡΤΟΚΑΛΙ (Μέτρια Δυσκολία)
else:
    current_color = [0, 255, 0, 160]    # ΠΡΑΣΙΝΟ (Εύκολο Parking)

# Δημιουργία DataFrame μόνο για την επιλεγμένη περιοχή για να αλλάζει ο κύκλος της
parking_data = pd.DataFrame({
    'lat': [view_centers[selected_zone]["lat"]],
    'lon': [view_centers[selected_zone]["lon"]],
    'name': [selected_zone],
    'color': [current_color], # Το χρώμα αλλάζει δυναμικά εδώ
    'radius': [50]
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
        map_style=None, # Χρήση default style για αποφυγή προβλημάτων Mapbox
        initial_view_state=new_view,
        layers=[
            pdk.Layer(
                'ScatterplotLayer',
                parking_data,
                get_position='[lon, lat]',
                get_fill_color='color', # Διαβάζει το δυναμικό χρώμα από το dataframe
                get_radius='radius',
                pickable=True,
            ),
        ],
    ))

with col2:
    st.subheader("📊 Analytics")
    st.metric("Πιθανότητα Εύρεσης", f"{prob}%")
    
    # Μικρή επεξήγηση χρώματος για το Report
    if prob > 60:
        st.error("Κατάσταση: Πολύ Αυξημένη Κίνηση")
    elif prob >= 35:
        st.warning("Κατάσταση: Μέτρια Διαθεσιμότητα")
    else:
        st.success("Κατάσταση: Υψηλή Διαθεσιμότητα")
        
    st.line_chart(np.random.randint(40, 90, size=(10, 1)))
