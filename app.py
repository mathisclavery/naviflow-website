"""Naviflow — interface de prédiction de fréquentation du métro parisien.

Flux : clic sur une station (carte) → sélection → choix date + horizon →
bouton « Lancer la prédiction » → l'API renvoie J+1..J+7.

Direction artistique : signalétique RATP poussée à fond —
  · carrelage métro biseauté en fond de page (texture CSS)
  · plaque émaillée verte pour l'identité et le nom de station
  · afficheur SIEL (matrice de points ambre) pour le chiffre de prédiction
  · pastilles de lignes M1–M14 aux couleurs officielles
  · ticket t+ en état vide
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
DATE_MIN = dt.date(2025, 6, 15)
DATE_MAX = dt.date(2025, 12, 31)
DATE_DEFAULT = dt.date(2025, 9, 1)

GEOJSON_PATH = "reseau_metro.geojson"

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
        <link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Hanken+Grotesk:wght@400;500;600;700&family=DotGothic16&display=swap" rel="stylesheet">
        <style>
            :root {
                --paper:#F2F0EA;
                --ink:#14141E;
                --ratp:#006A4E;
                --ratp-deep:#00543E;
                --amber:#FFB000;
                --siel-bg:#101524;
                --muted:#84847E;
                --hairline:#DEDBD0;
                --low:#3B6FB0; --high:#E2231A;
            }

            .stApp {
                background-color: var(--paper);
                background-image:
                    linear-gradient(rgba(20,20,30,.065) 1px, rgba(255,255,255,.55) 1px, transparent 2.5px),
                    linear-gradient(90deg, rgba(20,20,30,.045) 1px, rgba(255,255,255,.4) 1px, transparent 2.5px);
                background-size: 100% 36px, 96px 100%;
            }
            #MainMenu, header, footer { visibility:hidden; }

            html, body, [class*="css"] {
                font-family:'Hanken Grotesk', sans-serif; color:var(--ink);
            }
            h1,h2,h3 { font-family:'Bricolage Grotesque', sans-serif; letter-spacing:-0.02em; }
            .block-container { padding-top:2rem; max-width:1280px; }

            ::-webkit-scrollbar { width:9px; height:9px; }
            ::-webkit-scrollbar-thumb { background:var(--ratp); border-radius:99px; }
            ::-webkit-scrollbar-track { background:transparent; }

            @keyframes nfUp { from {opacity:0; transform:translateY(12px);} to {opacity:1; transform:none;} }
            @keyframes sielIn { 0%{opacity:0;} 35%{opacity:.7;} 45%{opacity:.15;} 60%{opacity:.9;} 70%{opacity:.4;} 100%{opacity:1;} }
            @keyframes blink { 0%,100%{opacity:1;} 50%{opacity:.15;} }

            .nf-header {
                display:flex; align-items:center; gap:1rem;
                margin-bottom:1.4rem; animation:nfUp .5s ease both;
            }
            .nf-roundel {
                width:52px; height:52px; border-radius:50%;
                background:#FFCD00; color:var(--ink);
                display:flex; align-items:center; justify-content:center;
                font-family:'Bricolage Grotesque'; font-weight:800; font-size:1.7rem;
                border:3px solid var(--ink);
                box-shadow:3px 3px 0 rgba(20,20,30,.18);
                flex:0 0 auto;
            }
            .nf-plaque {
                background:var(--ratp); color:#fff;
                border-radius:8px; padding:.55rem 1.4rem .6rem;
                box-shadow: inset 0 0 0 2px rgba(255,255,255,.9),
                            inset 0 0 0 4px var(--ratp),
                            0 8px 24px rgba(0,106,78,.28);
            }
            .nf-plaque .logo {
                font-family:'Bricolage Grotesque'; font-weight:800;
                font-size:1.9rem; line-height:1; letter-spacing:.04em;
            }
            .nf-headsub { color:var(--muted); font-size:.92rem; font-weight:500; }
            .nf-headsub b { color:var(--ink); font-weight:700; }

            .nf-planbar {
                display:flex; align-items:center; justify-content:space-between;
                gap:1rem; flex-wrap:wrap; margin:.2rem 0 .75rem;
                animation:nfUp .5s .08s ease both;
            }
            .nf-eyebrow {
                font-family:'Bricolage Grotesque'; font-weight:700; font-size:.74rem;
                letter-spacing:.16em; text-transform:uppercase; color:var(--ratp);
                display:flex; align-items:center; gap:.45rem;
            }
            .nf-eyebrow::before { content:""; width:9px; height:9px; background:var(--ratp); display:inline-block; }
            .nf-bullets { display:flex; gap:5px; flex-wrap:wrap; align-items:center; }
            .nf-bullet {
                width:23px; height:23px; border-radius:50%;
                display:flex; align-items:center; justify-content:center;
                font-family:'Bricolage Grotesque'; font-weight:800; font-size:.66rem;
                box-shadow: inset 0 -2px 0 rgba(0,0,0,.14);
            }
            .nf-gradlegend { display:flex; align-items:center; gap:.5rem; font-size:.8rem; color:var(--muted); }
            .nf-gradlegend .ramp {
                width:90px; height:9px; border-radius:99px;
                background:linear-gradient(90deg, var(--low), var(--high));
                border:1px solid rgba(20,20,30,.25);
            }

            iframe[title="streamlit_folium.st_folium"] {
                border:2.5px solid var(--ink) !important; border-radius:14px;
                box-shadow: 9px 9px 0 rgba(0,106,78,.16);
                animation:nfUp .55s .14s ease both;
            }

            section[data-testid="stSidebar"] {
                background:#FFFFFF; border-right:2px solid var(--ink);
            }
            section[data-testid="stSidebar"] > div { padding-top:.6rem; }
            section[data-testid="stSidebar"] .nf-eyebrow { margin:1.05rem 0 .4rem; }
            section[data-testid="stSidebar"] .block-container { animation:nfUp .5s .05s ease both; }

            /* widgets — texte en noir */
            div[data-baseweb="select"] > div {
                background:#fff; border:1.5px solid var(--ink); border-radius:10px;
                font-family:'Hanken Grotesk'; font-weight:500;
            }
            div[data-baseweb="select"] input,
            div[data-baseweb="select"] [data-testid="stSelectboxValue"],
            div[data-baseweb="select"] span,
            div[data-baseweb="select"] div {
                color: var(--ink) !important;
            }
            div[data-testid="stDateInput"] div[data-baseweb="input"] {
                background:#fff; border:1.5px solid var(--ink); border-radius:10px;
            }
            div[data-testid="stDateInput"] input {
                font-family:'Hanken Grotesk'; font-weight:500;
                color: var(--ink) !important;
            }

            div.stButton > button {
                width:100%; background:var(--ink); color:#fff; border:none;
                border-radius:10px; padding:.8rem 1rem;
                font-family:'Bricolage Grotesque'; font-weight:700;
                letter-spacing:.05em; font-size:.95rem; text-transform:uppercase;
                transition:transform .14s, box-shadow .14s, background .14s;
            }
            div.stButton > button:hover:enabled {
                background:var(--ratp); color:#fff;
                transform:translateY(-2px);
                box-shadow:0 8px 22px rgba(0,106,78,.35);
            }
            div.stButton > button:disabled { background:var(--hairline); color:var(--muted); }

            .nf-ticket {
                background:#fff; border:1.5px solid var(--ink); border-radius:10px;
                padding:.85rem 1rem 1.5rem; margin-top:1rem;
                position:relative; overflow:hidden;
                box-shadow:4px 4px 0 rgba(20,20,30,.08);
                font-size:.86rem; color:var(--muted); line-height:1.45;
            }
            .nf-ticket .tplus {
                font-family:'Bricolage Grotesque'; font-weight:800;
                color:#3F2A8F; font-size:1.05rem; margin-bottom:.2rem;
            }
            .nf-ticket::after {
                content:""; position:absolute; left:0; right:0; bottom:0; height:11px;
                background:repeating-linear-gradient(90deg,#433426 0 16px,#5C4936 16px 32px);
            }

            .nf-cartouche {
                background:var(--ratp); color:#fff; border-radius:12px;
                padding:1.05rem 1.1rem 1.15rem; margin-top:1rem;
                box-shadow: inset 0 0 0 2px rgba(255,255,255,.92),
                            inset 0 0 0 5px var(--ratp),
                            0 12px 30px rgba(0,84,62,.32);
                animation:nfUp .45s ease both;
            }
            .nf-cartouche .name {
                font-family:'Bricolage Grotesque'; font-weight:800;
                font-size:1.22rem; line-height:1.12; text-transform:uppercase;
                letter-spacing:.015em; word-break:break-word;
            }
            .nf-cartouche .meta { opacity:.82; font-size:.8rem; margin-top:.3rem; font-weight:500; }

            .nf-siel {
                background:var(--siel-bg); border-radius:9px;
                margin-top:.85rem; padding:.7rem .9rem .8rem;
                background-image:radial-gradient(rgba(255,176,0,.10) 1px, transparent 1.3px);
                background-size:7px 7px;
                box-shadow: inset 0 2px 10px rgba(0,0,0,.55);
            }
            .nf-siel .lbl {
                font-family:'Bricolage Grotesque'; font-weight:700; font-size:.62rem;
                letter-spacing:.22em; color:rgba(255,176,0,.65); text-transform:uppercase;
            }
            .nf-siel .num {
                font-family:'DotGothic16', monospace;
                color:var(--amber); line-height:1.05; margin-top:.15rem;
                text-shadow:0 0 12px rgba(255,176,0,.5), 0 0 3px rgba(255,176,0,.8);
                font-variant-numeric:tabular-nums; white-space:nowrap;
                animation:sielIn .8s steps(9) both;
            }
            .nf-siel .unit { font-size:.85rem; color:rgba(255,176,0,.7); margin-left:.3rem; }
            .nf-siel .dotblink {
                display:inline-block; width:7px; height:7px; border-radius:50%;
                background:var(--amber); margin-left:.5rem; vertical-align:middle;
                animation:blink 1.2s steps(1) infinite;
            }

            .nf-horizon-tag {
                display:inline-block; background:rgba(255,255,255,.16);
                border:1px solid rgba(255,255,255,.4);
                border-radius:999px; padding:.22rem .85rem; margin-top:.8rem;
                font-family:'Bricolage Grotesque'; font-weight:700; font-size:.74rem; letter-spacing:.05em;
            }

            .nf-bars { display:flex; gap:5px; align-items:flex-end; height:58px; margin-top:1rem; }
            .nf-bar { flex:1; border-radius:3px 3px 0 0; background:var(--hairline); transition:height .25s, background .25s; }
            .nf-bar.active { background:var(--amber); box-shadow:0 0 10px rgba(255,176,0,.45); }
            .nf-bars-lbl { display:flex; gap:5px; margin-top:.3rem; margin-bottom:1.2rem; }
            .nf-bars-lbl span { flex:1; text-align:center; font-size:.62rem; color:var(--muted); font-weight:600; }
            .nf-bars-lbl span.active { color:var(--ratp); font-weight:800; }

            .nf-warn {
                border:1.5px solid var(--high); border-radius:10px;
                padding:.9rem 1.1rem; color:var(--high); font-size:.88rem;
                background:rgba(226,35,26,.05); margin-top:1rem; font-weight:500;
            }
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
    try:
        with open(GEOJSON_PATH, encoding="utf-8") as f:
            gj = json.load(f)
    except FileNotFoundError:
        return []
    segments = []
    for feat in gj["features"]:
        name = feat["properties"].get("name", "")
        if name not in LIGNE_COLORS:
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
            latlon = [[pt[1], pt[0]] for pt in line]
            segments.append((latlon, color))
    return segments


def fetch_prediction(station_id: int, prediction_date: str):
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


def bullet_fg(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#14141E" if (.299 * r + .587 * g + .114 * b) > 150 else "#FFFFFF"


def bullets_html():
    out = []
    for name, color in LIGNE_COLORS.items():
        label = name.replace("Métro ", "").replace("bis", "b")
        out.append(
            f'<span class="nf-bullet" title="{name}" '
            f'style="background:{color};color:{bullet_fg(color)}">{label}</span>'
        )
    return "".join(out)


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
    """
    <div class="nf-header">
        <div class="nf-roundel">M</div>
        <div>
            <div class="nf-plaque"><span class="logo">NAVIFLOW</span></div>
        </div>
        <div class="nf-headsub">Prévision de fréquentation<br><b>Réseau Île-de-France Mobilités</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown('<div class="nf-eyebrow">Station</div>', unsafe_allow_html=True)

    labels = sorted(stations["LIBELLE_ARRET"].unique())
    options = ["— Choisir ou cliquer sur la carte —"] + labels

    sel = st.session_state.selected_id
    if sel is not None:
        cur_name = stations.loc[stations["ID_LIEU"] == sel, "LIBELLE_ARRET"].iloc[0]
        cur_index = options.index(cur_name) if cur_name in options else 0
    else:
        cur_index = 0

    chosen = st.selectbox("Station", options, index=cur_index,
                          label_visibility="collapsed")

    if chosen != "— Choisir ou cliquer sur la carte —":
        chosen_id = stations.loc[stations["LIBELLE_ARRET"] == chosen, "ID_LIEU"].iloc[0]
        if chosen_id != st.session_state.selected_id:
            st.session_state.selected_id = chosen_id
            st.session_state.result = None
            st.session_state.result_meta = None
            st.rerun()

    st.markdown('<div class="nf-eyebrow">Date de référence</div>', unsafe_allow_html=True)
    pred_date = st.date_input("Date", value=DATE_DEFAULT, min_value=DATE_MIN,
                              max_value=DATE_MAX, label_visibility="collapsed", format="DD/MM/YYYY")

    st.markdown('<div class="nf-eyebrow">Horizon de prévision</div>', unsafe_allow_html=True)
    horizon = st.slider("Horizon", 1, HORIZON_MAX, 1, format="J+%d", label_visibility="collapsed")

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
    sel = st.session_state.selected_id
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
        formatted = f"{value:,.0f}".replace(",", " ")
        n_digits = sum(c.isdigit() for c in formatted)
        font_size = 2.9 if n_digits <= 4 else (2.4 if n_digits <= 6 else 2.0)
        st.markdown(
            f"""
            <div class="nf-cartouche">
                <div class="name">{name}</div>
                <div class="meta">Validations prévues · {(rdate + dt.timedelta(days=horizon)).strftime('%d/%m/%Y')}</div>
                <div class="nf-siel">
                    <div class="lbl">Affichage prévision<span class="dotblink"></span></div>
                    <div class="num" style="font-size:{font_size}rem">{formatted}<span class="unit">valid.</span></div>
                </div>
                <div class="nf-horizon-tag">HORIZON J+{horizon}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        vmax = max(res.values())
        bars = "".join(
            f'<div class="{"nf-bar active" if h == horizon else "nf-bar"}" '
            f'style="height:{8 + 50 * (res[h] / vmax if vmax else 0):.0f}px"></div>'
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

    else:
        st.markdown(
            """
            <div class="nf-ticket">
                <div class="tplus">t+</div>
                Choisissez une station sur la carte ou dans la liste
                puis lancez la prédiction pour afficher la fréquentation prévue.
            </div>
            """,
            unsafe_allow_html=True,
        )

# --------------------------------------------------------------------------- #
# Carte
# --------------------------------------------------------------------------- #
st.markdown(
    f"""
    <div class="nf-planbar">
        <div class="nf-eyebrow">Plan du réseau</div>
        <div class="nf-bullets">{bullets_html()}</div>
        <div class="nf-gradlegend">affluence&nbsp;faible <span class="ramp"></span> forte</div>
    </div>
    """,
    unsafe_allow_html=True,
)

aff_max = stations["affluence_moyenne"].max()
aff_min = stations["affluence_moyenne"].min()

m = folium.Map(location=[48.8566, 2.3522], zoom_start=12, tiles="CartoDB positron")

for latlon, color in metro_lines:
    folium.PolyLine(latlon, color=color, weight=3, opacity=0.55).add_to(m)

for _, r in stations.iterrows():
    is_sel = (r["ID_LIEU"] == st.session_state.selected_id)
    rayon = 4 + 11 * (r["affluence_moyenne"] / aff_max if aff_max else 0)
    couleur = "#14141E" if is_sel else color_for(r["affluence_moyenne"], aff_min, aff_max)
    folium.CircleMarker(
        location=[r["lat"], r["lon"]],
        radius=rayon + (3 if is_sel else 0),
        tooltip=r["LIBELLE_ARRET"],
        color="#000000" if is_sel else couleur,
        weight=2.5 if is_sel else 1,
        fill=True, fill_color=couleur, fill_opacity=0.9 if is_sel else 0.62,
    ).add_to(m)

out = st_folium(m, width=1100, height=620, returned_objects=["last_object_clicked"])

clicked = out.get("last_object_clicked")
if clicked:
    d = (stations["lat"] - clicked["lat"]) ** 2 + (stations["lon"] - clicked["lng"]) ** 2
    nearest = stations.loc[d.idxmin(), "ID_LIEU"]
    if nearest != st.session_state.selected_id:
        st.session_state.selected_id = nearest
        st.session_state.result = None
        st.session_state.result_meta = None
        st.rerun()