import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

API_URL = st.secrets["API_URL"]

st.title("Naviflow — Prédiction de fréquentation du métro parisien")

# ─── CARTE DES STATIONS ───────────────────────────────
st.header("Carte des stations")

@st.cache_data
def load_coords():
    return pd.read_csv("gares_coords.csv")

stations = load_coords()
geo = stations.dropna(subset=["lat", "lon"])

m = folium.Map(location=[48.8566, 2.3522], zoom_start=11, tiles="CartoDB positron")
aff_max = geo["affluence_moyenne"].max()

for _, row in geo.iterrows():
    rayon = 3 + 12 * (row["affluence_moyenne"] / aff_max)
    couleur = "#E24B4A" if row["ID_LIEU"] < 0 else "#3186CC"
    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=rayon,
        popup=f"{row['LIBELLE_ARRET']}<br>{row['affluence_moyenne']:,.0f} valid./jour",
        tooltip=row["LIBELLE_ARRET"],
        color=couleur, fill=True, fill_opacity=0.6, weight=1,
    ).add_to(m)

st_folium(m, width=900, height=600)
