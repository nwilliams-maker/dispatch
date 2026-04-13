import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
import json
from datetime import datetime, timedelta
from streamlit_folium import st_folium
import folium
import threading

# --- CONFIG & CREDENTIALS ---
# Accessing secrets safely
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"
SAVED_ROUTES_GID = "1477617688"
ACCEPTED_ROUTES_GID = "934075207"
DECLINED_ROUTES_GID = "600909788"

# Terraboost Media Brand Palette
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_APP_BG = "#f1f5f9"
TB_HOVER_GRAY = "#e2e8f0"
TB_GREEN_FILL = "#dcfce7"
TB_BLUE_FILL = "#dbeafe" 
TB_RED_FILL = "#ffcccc" 

POD_CONFIGS = {
    "Blue": {"states": {"AL", "AR", "FL", "IL", "IA", "LA", "MI", "MN", "MS", "MO", "NC", "SC", "WI"}},
    "Green": {"states": {"CO", "DC", "GA", "IN", "KY", "MD", "NJ", "OH", "UT"}},
    "Orange": {"states": {"AK", "AZ", "CA", "HI", "ID", "NV", "OR", "WA"}},
    "Purple": {"states": {"KS", "MT", "NE", "NM", "ND", "OK", "SD", "TN", "TX", "WY"}},
    "Red": {"states": {"CT", "DE", "ME", "MA", "NH", "NY", "PA", "RI", "VT", "VA", "WV"}}
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

st.set_page_config(page_title="Dispatch Command Center", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    .stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
    
    /* Layout Tightening */
    .main .block-container {{ max-width: 1200px !important; padding-top: 2rem; }}
    
    /* Tab Styling */
    .stTabs [data-baseweb="tab-list"] {{ justify-content: center; gap: 12px; background: transparent !important; padding-bottom: 20px; border-bottom: 2px solid #cbd5e1 !important; }}
    .stTabs [data-baseweb="tab"] {{ border-radius: 30px !important; margin: 0 5px !important; font-weight: 800 !important; padding: 8px 25px !important; border: 2px solid #cbd5e1 !important; background: white !important; }}
    .stTabs [aria-selected="true"] {{ transform: translateY(-4px) !important; box-shadow: 0 10px 20px rgba(99, 48, 148, 0.2) !important; border-color: {TB_PURPLE} !important; }}

    /* Button Styling */
    button[kind="primary"] {{ background-color: {TB_GREEN} !important; border: none !important; font-weight: 800 !important; border-radius: 8px !important; }}
    button[kind="secondary"] {{ border: 2px solid {TB_PURPLE} !important; color: {TB_PURPLE} !important; font-weight: 800 !important; }}

    /* Card Hover Effects */
    div[data-testid="stExpander"] {{ border-radius: 12px !important; border: 1px solid #cbd5e1 !important; transition: all 0.3s ease !important; }}
    div[data-testid="stExpander"]:hover {{ box-shadow: 0 8px 16px rgba(0,0,0,0.1) !important; transform: translateY(-2px); }}
    
    /* Utility */
    .loading-pulse {{ animation: pulse 1.5s infinite; }}
    @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.5; }} 100% {{ opacity: 1; }} }}
</style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_state(st_str):
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

@st.cache_data(ttl=15, show_spinner=False)
def fetch_sent_records_from_sheet():
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets_to_fetch = [
            (DECLINED_ROUTES_GID, "declined"),
            (ACCEPTED_ROUTES_GID, "accepted"),
            (SAVED_ROUTES_GID, "sent")
        ]
        sent_dict, ghost_routes = {}, {k: [] for k in POD_CONFIGS.keys()}
        ghost_routes["UNKNOWN"] = []

        for gid, status_label in sheets_to_fetch:
            df = pd.read_csv(base_url + gid)
            df.columns = [str(c).strip().lower() for c in df.columns]
            if 'json payload' in df.columns:
                for _, row in df.iterrows():
                    try:
                        p = json.loads(row['json payload'])
                        tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                        c_name = row.get('contractor', 'Unknown')
                        ts = row.get('date created', '')
                        
                        for tid in tids:
                            if tid.strip():
                                sent_dict[tid.strip()] = {"name": c_name, "status": status_label, "time": ts}
                        
                        if status_label == 'accepted':
                            # Pod logic for ghosts
                            ghost_routes["Blue"].append({"contractor_name": c_name, "tasks": len(tids)}) # Simplified for example
                    except: continue
        return sent_dict, ghost_routes
    except: return {}, {}

@st.cache_data(show_spinner=False)
def get_gmaps(home, waypoints):
    if not waypoints: return 0, 0, "0h 0m"
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints[:23])}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return 0, 0, "0h 0m"

# --- CORE PROCESSING ---
def process_pod(pod_name, master_bar=None, pod_idx=0, total_pods=1):
    config = POD_CONFIGS[pod_name]
    # Internal progress mapping
    pod_weight = 1.0 / total_pods
    start_pct = pod_idx * pod_weight
    prog_bar = master_bar if master_bar else st.progress(0)

    try:
        # Fetch logic (Simplified for logic check)
        # 1. Fetch Onfleet Teams
        # 2. Fetch Tasks (last 80 days)
        # 3. Cluster (Haversine 50mi, Max 20 stops)
        # 4. Save to session_state[f"clusters_{pod_name}"]
        time.sleep(1) # Simulating API latency
        st.session_state[f"clusters_{pod_name}"] = [] # Placeholder
    except Exception as e:
        st.error(f"Error in {pod_name}: {e}")

# --- UI COMPONENTS ---
def render_dispatch_card(i, cluster, pod_name, status_context="ready"):
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    
    # Pricing State Logic
    pay_key = f"pay_{cluster_hash}"
    rate_key = f"rate_{cluster_hash}"
    
    with st.container():
        col1, col2, col3 = st.columns([2, 1, 1])
        # Add your inputs here...
        st.write(f"Route Hash: {cluster_hash}")

# --- MAIN APP ---
def main():
    # Logo
    st.markdown("<h1 style='text-align: center; color: #633094;'>Dispatch Command Center</h1>", unsafe_allow_html=True)
    
    if "ic_df" not in st.session_state:
        st.session_state.ic_df = pd.DataFrame() # Load your CSV here

    tabs = st.tabs(["Global", "Blue Pod", "Green Pod", "Orange Pod", "Purple Pod", "Red Pod"])

    with tabs[0]:
        st.subheader("Global Overview")
        if st.button("Initialize All Pods", type="primary"):
            st.session_state.trigger_pull = True
            st.rerun()

    # Dynamic Pod Tabs
    for idx, pod in enumerate(["Blue", "Green", "Orange", "Purple", "Red"], 1):
        with tabs[idx]:
            st.header(f"{pod} Region")
            if f"clusters_{pod}" not in st.session_state:
                if st.button(f"Load {pod} Data", key=f"load_{pod}"):
                    process_pod(pod)
                    st.rerun()

if __name__ == "__main__":
    main()
