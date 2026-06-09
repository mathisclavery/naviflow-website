import streamlit as st
import requests

API_URL = st.secrets["API_URL"]

st.title("Naviflow — Prédiction de fréquentation du métro parisien")

# Test de connexion à l'API
if st.button("Tester la connexion à l'API"):
    response = requests.get(f"{API_URL}/ping")
    if response.status_code == 200:
        st.success(f"API connectée ✅ — {response.json()}")
    else:
        st.error(f"Erreur {response.status_code}")

# Test d'une prédiction
station_id = st.number_input("Station ID", value=59403, step=1)
prediction_date = st.text_input("Date de prédiction", value="2024-01-15")

if st.button("Prédire"):
    response = requests.get(
        f"{API_URL}/predict",
        params={"station_id": station_id, "prediction_date": prediction_date}
    )
    if response.status_code == 200:
        st.json(response.json())
    else:
        st.error(f"Erreur {response.status_code} : {response.text}")
