"""Naviflow — interface de prédiction de fréquentation du métro parisien.

Flux : clic sur une station (carte) → sélection → choix date + horizon →
bouton « Lancer la prédiction » → l'API renvoie J+1..J+7.

La carte trace les lignes de métro M1–M14 à leurs couleurs officielles RATP
(fond), puis pose les stations dimensionnées par affluence moyenne (dessus).

Style : signalétique RATP (vert réseau, cartouche de quai) + dashboard épuré.
"""

import datetime as dt
import json

import folium
import pandas as pd
import requests
import streamlit as st
from streamlit_folium import st_folium

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
API_URL = st.secrets["API_URL"]

HORIZON_MAX = 7
DATE_MIN = dt.date(2025, 6, 15)     # ~200 derniers jours de 2025 (jeu de test)
DATE_MAX = dt.date(2025, 12, 31)
DATE_DEFAULT = dt.date(2025, 9, 1)

GEOJSON_PATH = "reseau_metro.geojson"

# Couleurs officielles RATP par ligne (le GeoJSON umap donne des approximations CSS)
LIGNE_COLORS = {
    "Métro 1": "#FFCD00", "Métro 2": "#003CA6", "Métro 3": "#837902",
    "Métro 3bis": "#6EC4E8", "Métro 4": "#CF009E", "Métro 5": "#FF7E2E",
    "Métro 6": "#6ECA97", "Métro 7": "#FA9ABA", "Métro 7bis": "#6ECA97",
    "Métro 8": "#E19BDF", "Métro 9": "#B6BD00", "Métro 10": "#C9910D",
    "Métro 11": "#704B1C", "Métro 12": "#007852", "Métro 13": "#6EC4E8",
    "Métro 14": "#62259D",
}

st.set_page_config(page_title="Naviflow", page_icon="🚇", layout="wide",
                   initial_sidebar_state="expanded")


# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
def inject_style():
    st.markdown(
        """
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800;900&family=Inter+Tight:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --paper:#FAFAF8; --ink:#15151F; --ratp:#006A4E;
                --muted:#8A8A96; --hairline:#E6E6E0;
                --low:#3B6FB0; --high:#E2231A;
            }
            .stApp { background: var(--paper); }
            #MainMenu, header, footer { visibility: hidden; }
            html, body, [class*="css"] { font-family:'Inter Tight',sans-serif; color:var(--ink); }
            h1,h2,h3 { font-family:'Archivo',sans-serif; letter-spacing:-0.02em; }

            .block-container { padding-top:2.2rem; }

            .nf-header {
                display:flex; align-items:baseline; gap:.9rem;
                border-bottom:2px solid var(--ink); padding-bottom:.7rem; margin-bottom:1.3rem;
            }
            .nf-logo { font-family:'Archivo',sans-serif; font-weight:900; font-size:2rem; color:var(--ratp); line-height:1; letter-spacing:-0.03em; }
            .nf-sub { color:var(--muted); font-size:.95rem; font-weight:500; }

            section[data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--hairline); }
            /* sidebar figée + contenu centré verticalement, sans scroll */
            section[data-testid="stSidebar"] > div {
                position:sticky; top:0; height:100vh; overflow:hidden;
            }
            section[data-testid="stSidebar"] .block-container {
                display:flex; flex-direction:column; justify-content:flex-start;
                height:100vh; padding-top:1rem; padding-bottom:2.5rem;
            }
            /* premier eyebrow (STATION) sans grande marge en haut */
            section[data-testid="stSidebar"] .nf-eyebrow:first-of-type { margin-top:0; }

            .nf-eyebrow {
                font-family:'Archivo',sans-serif; font-weight:700; font-size:.72rem;
                letter-spacing:.14em; text-transform:uppercase; color:var(--muted); margin:1rem 0 .35rem;
            }

            div.stButton > button {
                width:100%; background:var(--ink); color:#fff; border:none;
                border-radius:10px; padding:.75rem 1rem; font-family:'Archivo',sans-serif;
                font-weight:700; letter-spacing:.02em; font-size:.95rem;
                transition:transform .12s, box-shadow .12s, background .12s;
            }
            div.stButton > button:hover { transform:translateY(-1px); box-shadow:0 6px 18px rgba(21,21,31,.22); background:#000; color:#fff; }
            div.stButton > button:disabled { background:var(--hairline); color:var(--muted); transform:none; box-shadow:none; }

            /* cartouche de quai — signature, fond vert RATP façon plaque émaillée */
            .nf-cartouche {
                background:var(--ratp); color:#fff; border-radius:16px;
                padding:1.3rem 1.5rem; margin-top:.9rem;
                box-shadow:0 10px 32px rgba(0,106,78,.24);
                position:relative; overflow:hidden;
            }
            .nf-cartouche::before {
                content:""; position:absolute; top:0; left:0; width:5px; height:100%;
                background:rgba(255,255,255,.55);
            }
            .nf-cartouche .name { font-family:'Archivo',sans-serif; font-weight:700; font-size:1.25rem; line-height:1.15; padding-left:.4rem; word-break:break-word; }
            .nf-cartouche .meta { opacity:.8; font-size:.82rem; margin-top:.25rem; padding-left:.4rem; }
            .nf-bignum { font-family:'Archivo',sans-serif; font-weight:900; line-height:1; margin-top:.9rem; padding-left:.4rem; font-variant-numeric:tabular-nums; letter-spacing:-0.02em; white-space:nowrap; }
            .nf-bignum .unit { font-size:.9rem; font-weight:600; opacity:.7; letter-spacing:0; }
            .nf-horizon-tag { display:inline-block; background:rgba(255,255,255,.18); border-radius:999px; padding:.22rem .8rem; margin:.8rem 0 0 .4rem; font-weight:700; font-size:.76rem; letter-spacing:.02em; font-family:'Archivo',sans-serif; }

            .nf-selected { font-family:'Archivo',sans-serif; font-weight:700; font-size:1.1rem; margin-top:.2rem; color:var(--ink); }

            .nf-empty, .nf-warn {
                border:1px dashed var(--hairline); border-radius:14px;
                padding:1rem 1.2rem; color:var(--muted); font-size:.9rem; margin-top:.6rem;
            }
            .nf-warn { border-color:var(--high); color:var(--high); background:rgba(226,35,26,.04); }

            .nf-bars { display:flex; gap:5px; align-items:flex-end; height:60px; margin-top:1.1rem; }
            .nf-bar { flex:1; border-radius:3px 3px 0 0; background:var(--hairline); transition:height .25s, background .25s; }
            .nf-bar.active { background:var(--ratp); }
            .nf-bars-lbl { display:flex; gap:5px; margin-top:.3rem; margin-bottom:1.5rem; }
            .nf-bars-lbl span { flex:1; text-align:center; font-size:.62rem; color:var(--muted); font-weight:500; }
            .nf-bars-lbl span.active { color:var(--ratp); font-weight:700; }

            .nf-legend { display:flex; gap:1.3rem; align-items:center; font-size:.82rem; color:var(--muted); margin:.1rem 0 .7rem; flex-wrap:wrap; }
            .nf-legend .dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:.35rem; vertical-align:middle; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #
@st.cache_data
def load_coords():
    df = pd.read_csv("stations_coords.csv")
    return df.dropna(subset=["lat", "lon"])


@st.cache_data
def load_metro_lines():
    """Renvoie la liste des tracés métro : [(coords_latlon, couleur_officielle)]."""
    with open(GEOJSON_PATH, encoding="utf-8") as f:
        gj = json.load(f)

    segments = []
    for feat in gj["features"]:
        name = feat["properties"].get("name", "")
        if name not in LIGNE_COLORS:           # ne garde que M1–M14
            continue
        color = LIGNE_COLORS[name]
        geom = feat["geometry"]
        if geom["type"] == "LineString":
            polylines = [geom["coordinates"]]
        elif geom["type"] == "MultiLineString":
            polylines = geom["coordinates"]
        else:
            continue
        for line in polylines:
            latlon = [[pt[1], pt[0]] for pt in line]   # geojson = [lon, lat]
            segments.append((latlon, color))
    return segments


def fetch_prediction(station_id: int, prediction_date: str):
    """Renvoie (dict {1:.., ..7:..}, None) ou (None, message d'erreur)."""
    try:
        r = requests.get(
            f"{API_URL}/predict",
            params={"station_id": int(station_id), "prediction_date": prediction_date},
            timeout=30,
        )
        if r.status_code == 200:
            preds = r.json()["predictions"]
            return {int(k.split("+")[1]): float(v) for k, v in preds.items()}, None
        return None, r.json().get("detail", f"Erreur {r.status_code}")
    except requests.RequestException as e:
        return None, f"API injoignable ({e})"


def color_for(value, vmin, vmax):
    t = 0.5 if vmax <= vmin else max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
    low, high = (59, 111, 176), (226, 35, 26)
    return "#%02X%02X%02X" % tuple(round(low[i] + t * (high[i] - low[i])) for i in range(3))


# --------------------------------------------------------------------------- #
# État
# --------------------------------------------------------------------------- #
inject_style()
stations = load_coords()
metro_lines = load_metro_lines()

st.session_state.setdefault("selected_id", None)
st.session_state.setdefault("result", None)
st.session_state.setdefault("result_meta", None)

# --------------------------------------------------------------------------- #
# En-tête
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="nf-header"><span class="nf-logo">NAVIFLOW</span>'
    '<span class="nf-sub">Prévision de fréquentation · réseau métro francilien</span></div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Sidebar — contrôles
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown('<div class="nf-eyebrow">Station</div>', unsafe_allow_html=True)

    # liste triée des libellés ; le selectbox offre l'autocomplétion native
    labels = sorted(stations["LIBELLE_ARRET"].unique())
    options = ["— Choisir ou cliquer sur la carte —"] + labels

    # index courant déduit de la station sélectionnée (clic carte OU choix précédent)
    sel = st.session_state.selected_id
    if sel is not None:
        cur_name = stations.loc[stations["ID_LIEU"] == sel, "LIBELLE_ARRET"].iloc[0]
        cur_index = options.index(cur_name) if cur_name in options else 0
    else:
        cur_index = 0

    chosen = st.selectbox("Station", options, index=cur_index,
                          label_visibility="collapsed")

    # si l'utilisateur a choisi un libellé dans la liste, on met à jour la sélection
    if chosen != "— Choisir ou cliquer sur la carte —":
        chosen_id = stations.loc[stations["LIBELLE_ARRET"] == chosen, "ID_LIEU"].iloc[0]
        if chosen_id != st.session_state.selected_id:
            st.session_state.selected_id = chosen_id
            st.session_state.result = None
            st.session_state.result_meta = None
            st.rerun()

    st.markdown('<div class="nf-eyebrow">Date de référence</div>', unsafe_allow_html=True)
    pred_date = st.date_input("Date", value=DATE_DEFAULT, min_value=DATE_MIN,
                              max_value=DATE_MAX, label_visibility="collapsed")

    st.markdown('<div class="nf-eyebrow">Horizon de prévision</div>', unsafe_allow_html=True)
    horizon = st.slider("Horizon", 1, HORIZON_MAX, 1, format="J+%d", label_visibility="collapsed")

    st.markdown('<div class="nf-eyebrow">&nbsp;</div>', unsafe_allow_html=True)
    sel = st.session_state.selected_id   # valeur à jour (clic carte ou selectbox)
    launch = st.button("Lancer la prédiction", disabled=(sel is None))

    if launch and sel is not None:
        preds, err = fetch_prediction(sel, pred_date.isoformat())
        if err:
            st.session_state.result = None
            st.session_state.result_meta = err
        else:
            st.session_state.result = preds
            st.session_state.result_meta = (sel, pred_date)

    res = st.session_state.result
    meta = st.session_state.result_meta
    if res is not None and isinstance(meta, tuple):
        rid, rdate = meta
        name = stations.loc[stations["ID_LIEU"] == rid, "LIBELLE_ARRET"].iloc[0]
        value = res[horizon]
        # taille du chiffre adaptée à sa longueur (évite le débordement sur 6+ chiffres)
        formatted = f"{value:,.0f}".replace(",", " ")
        n_digits = sum(c.isdigit() for c in formatted)
        font_size = 3.3 if n_digits <= 4 else (2.7 if n_digits <= 6 else 2.2)
        st.markdown(
            f"""
            <div class="nf-cartouche">
                <div class="name">{name}</div>
                <div class="meta">Validations prévues · {rdate.strftime('%d/%m/%Y')}</div>
                <div class="nf-bignum" style="font-size:{font_size}rem">{formatted}<span class="unit"> valid.</span></div>
                <div class="nf-horizon-tag">Horizon J+{horizon}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        vmax = max(res.values())
        bars = "".join(
            f'<div class="{"nf-bar active" if h == horizon else "nf-bar"}" '
            f'style="height:{8 + 52 * (res[h] / vmax if vmax else 0):.0f}px"></div>'
            for h in range(1, HORIZON_MAX + 1)
        )
        lbls = "".join(
            f'<span class="{"active" if h == horizon else ""}">{h}</span>'
            for h in range(1, HORIZON_MAX + 1)
        )
        st.markdown(f'<div class="nf-bars">{bars}</div><div class="nf-bars-lbl">{lbls}</div>',
                    unsafe_allow_html=True)
    elif isinstance(meta, str):
        st.markdown(f'<div class="nf-warn">{meta}</div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# Carte
# --------------------------------------------------------------------------- #
st.markdown(
    '<div class="nf-legend">'
    '<span><span class="dot" style="background:var(--low)"></span>affluence faible</span>'
    '<span><span class="dot" style="background:var(--high)"></span>affluence forte</span>'
    '<span><span class="dot" style="background:var(--ink)"></span>station sélectionnée</span>'
    '<span>· lignes M1–M14 aux couleurs RATP</span>'
    '</div>',
    unsafe_allow_html=True,
)

aff_max = stations["affluence_moyenne"].max()
aff_min = stations["affluence_moyenne"].min()

m = folium.Map(location=[48.8566, 2.3522], zoom_start=12, tiles="CartoDB positron")

# 1) lignes de métro en fond
for latlon, color in metro_lines:
    folium.PolyLine(latlon, color=color, weight=3, opacity=0.55).add_to(m)

# 2) stations par-dessus
for _, r in stations.iterrows():
    is_sel = (r["ID_LIEU"] == st.session_state.selected_id)
    rayon = 4 + 11 * (r["affluence_moyenne"] / aff_max if aff_max else 0)
    couleur = "#15151F" if is_sel else color_for(r["affluence_moyenne"], aff_min, aff_max)
    folium.CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=rayon + (3 if is_sel else 0),
        tooltip=r["LIBELLE_ARRET"],
        color="#FFFFFF" if is_sel else couleur,
        weight=2.5 if is_sel else 1,
        fill=True, fill_color=couleur, fill_opacity=0.9 if is_sel else 0.62,
    ).add_to(m)

out = st_folium(m, width=1100, height=620, returned_objects=["last_object_clicked"])

# clic → sélection de la station la plus proche
clicked = out.get("last_object_clicked")
if clicked:
    d = (stations["lat"] - clicked["lat"]) ** 2 + (stations["lon"] - clicked["lng"]) ** 2
    nearest = stations.loc[d.idxmin(), "ID_LIEU"]
    if nearest != st.session_state.selected_id:
        st.session_state.selected_id = nearest
        st.session_state.result = None
        st.session_state.result_meta = None
        st.rerun()
