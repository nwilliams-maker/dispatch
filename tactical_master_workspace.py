import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

MAX_DEADHEAD_MILES = 60
HOURLY_FLOOR_RATE = 25.00
REVIEW_PER_STOP_LIMIT = 23.00 

TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_RED = "#ef4444"
TB_BLUE = "#3b82f6"
TB_LIGHT_BLUE = "#e6f0fa"

POD_CONFIGS = {
    "Blue Pod": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}, "color": "blue"},
    "Green Pod": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}, "color": "green"},
    "Orange Pod": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}, "color": "orange"},
    "Purple Pod": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}, "color": "purple"},
    "Red Pod": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}, "color": "red"}
}

STATE_MAP = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC"
}

headers = {"Authorization": f"Basic {base64.b64encode(f'{ONFLEET_KEY}:'.encode()).decode()}"}

st.set_page_config(page_title="Terraboost Tactical Workspace", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');
    .stApp {{ background-color: #f4f5f7 !important; color: #000000 !important; font-family: 'Roboto', sans-serif !important; }}
    h1, h2, h3 {{ color: {TB_PURPLE} !important; font-weight: 800 !important; }}
    div[data-testid="stExpander"] {{ border: 1px solid #d0d4e4 !important; border-radius: 8px !important; margin-bottom: 12px; background: white; }}
    div[data-testid="stExpander"] details summary {{ background-color: {TB_LIGHT_BLUE} !important; padding: 12px !important; border-radius: 8px 8px 0 0 !important; }}
    div[data-testid="stTextArea"] textarea {{ color: #000000 !important; background-color: #FFFFFF !important; border: 2px solid {TB_PURPLE} !important; font-weight: 600 !important; }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: #FFFFFF !important; font-weight: 700 !important; border-radius: 6px !important; width: 100%; }}
    .stButton>button:hover {{ background-color: {TB_GREEN} !important; }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

@st.cache_data(show_spinner=False, ttl=86400)
def fetch_metrics_with_return(home, stops, rate):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(stops[:10])}&key={GOOGLE_MAPS_KEY}"
    res = requests.get(url).json()
    mi, hrs, t_str = 0, 0, "0h 0m"
    if res['status'] == 'OK':
        mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
        hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
        t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    pay = max(len(stops) * rate, hrs * HOURLY_FLOOR_RATE)
    return round(mi, 1), t_str, round(pay, 2)

@st.cache_data(ttl=600)
def load_ic_database(sheet_url):
    try: return pd.read_csv(f"{sheet_url.split('/edit')[0]}/export?format=csv&gid=0")
    except: return None

# --- DISPATCH RENDER ---
def render_dispatch_logic(i, cluster, pod_name, is_sent=False):
    cluster_hash = hashlib.md5("".join(sorted([t['id'] for t in cluster['data']])).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_gas_id = st.session_state.get(sync_key, None)

    loc_sum = {}
    for c in cluster['data']:
        addr = c['full_addr']; loc_sum[addr] = loc_sum.get(addr, 0) + 1
    
    ic_df = st.session_state.ic_df.dropna(subset=['Lat', 'Lng'])
    ic_df['d'] = ic_df.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
    valid_ics = ic_df[ic_df['d'] <= MAX_DEADHEAD_MILES].sort_values('d').head(5)

    if valid_ics.empty: st.error("No contractors nearby."); return

    ic_opts = {f"{row['Name']} ({round(row['d'], 1)} mi)": row for _, row in valid_ics.iterrows()}
    sel_label = st.selectbox("Contractor", list(ic_opts.keys()), key=f"s_{i}")
    rate = st.number_input("Rate/Stop", 16.0, 100.0, 18.0, key=f"r_{i}")
    
    sel_ic = ic_opts[sel_label]
    mi, t_str, pay = fetch_metrics_with_return(sel_ic['Location'], list(loc_sum.keys()), rate)
    
    wo_title = f"{sel_ic['Name'][:3].upper()}-{datetime.now().strftime('%m%d%H%M')}"
    sig = (f"Work Order: {wo_title}\nPay: ${pay:.2f}\nStops: {cluster['unique_count']}\n"
           f"Authorize: {PORTAL_BASE_URL}?route={real_gas_id or 'PENDING'}&v2=true")
    
    st.text_area("Email Payload", sig, height=180, key=f"area_{i}_{sel_ic['Name']}_{rate}")

    if st.button("☁️ Sync & Generate Link", key=f"btn_{i}"):
        payload = {
            "icn": sel_ic['Name'], "wo": wo_title, "comp": pay, 
            "lCnt": cluster['unique_count'], "mi": mi, "time": t_str,
            "ic_home": sel_ic['Location'], 
            "locs": " | ".join(list(loc_sum.keys())),
            "taskIds": ",".join([t['id'] for t in cluster['data']])
        }
        res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
        if res.get("success"):
            st.session_state[sync_key] = res['routeId']
            st.rerun()

# (Processing and Tab logic remains same as provided in previous turns)
