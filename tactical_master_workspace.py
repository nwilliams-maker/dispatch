import streamlit as st
import requests
import base64
import math
import pandas as pd
import time
import hashlib
from datetime import datetime, timedelta

# --- CONFIG & CREDENTIALS ---
ONFLEET_KEY = st.secrets["ONFLEET_KEY"]
GOOGLE_MAPS_KEY = st.secrets["GOOGLE_MAPS_KEY"]
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycbynAIziubArSQ0hVGTvJMpk11a9yLP0kNcSmGpcY7GDNRT25Po5p92K3EDslx9VycKC/exec"
PORTAL_BASE_URL = "https://nwilliams-maker.github.io/Route-Authorization-Portal/portal-v2.html"
IC_SHEET_URL = "https://docs.google.com/spreadsheets/d/1y6wX0x93iDc3gdK_nZKLD-2QcGkUHkcM75u90ffRO6k/edit#gid=0"

HOURLY_FLOOR_RATE = 25.00
TB_PURPLE = "#633094"
TB_GREEN = "#76bc21"
TB_LIGHT_BLUE = "#e6f0fa"

st.set_page_config(page_title="Network Command Center", layout="wide")

# --- UI STYLING ---
st.markdown(f"""
    <style>
    .stApp {{ background-color: #f4f5f7; color: black; font-family: 'Roboto', sans-serif; }}
    div[data-testid="stExpander"] {{ border: 1px solid #d0d4e4; border-radius: 12px; background-color: white; }}
    div[data-testid="stExpander"] details summary {{ background-color: {TB_LIGHT_BLUE}; padding: 15px; border-radius: 12px 12px 0 0; }}
    div[data-testid="stTextArea"] textarea {{ color: black; background-color: white; border: 2px solid {TB_PURPLE}; font-weight: 500; }}
    .stButton>button {{ background-color: {TB_PURPLE} !important; color: white !important; font-weight: 700; border-radius: 8px; }}
    .stButton>button:hover {{ background-color: {TB_GREEN} !important; }}
    </style>
""", unsafe_allow_html=True)

# --- UTILITIES ---
@st.cache_data(ttl=600)
def load_ics():
    return pd.read_csv(f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid=0")

def fetch_metrics(home_addr, stops, rate):
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home_addr}&destination={home_addr}&waypoints=optimize:true|{'|'.join(stops[:10])}&key={GOOGLE_MAPS_KEY}"
    res = requests.get(url).json()
    mi, hrs, t_str = 0, 0, "0h 0m"
    if res['status'] == 'OK':
        mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
        hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
        t_str = f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    pay = max(len(stops) * rate, hrs * HOURLY_FLOOR_RATE)
    return round(mi, 1), t_str, round(pay, 2)

# --- RENDER CARD ---
def render_dispatch_logic(i, cluster, pod_name):
    ic_df = st.session_state.ic_df.dropna(subset=['Lat', 'Lng'])
    # ... (Clustering and filtering logic) ...
    
    sel_ic = st.selectbox("Contractor", ic_df['Name'], key=f"sel_{i}")
    row = ic_df[ic_df['Name'] == sel_ic].iloc[0]
    
    rate = st.number_input("Rate/Stop", 16.0, 100.0, 18.0, key=f"rate_{i}")
    mi, t_str, pay = fetch_metrics(row['Location'], [t['addr'] for t in cluster['data']], rate)
    
    wo_title = f"{row['Name'][:3].upper()}-{datetime.now().strftime('%m%d%H%M')}"
    
    # 🎯 Dynamic Email Payload
    sig = (f"Work Order: {wo_title}\n"
           f"Compensation: ${pay}\n"
           f"Stops: {cluster['unique_count']}\n"
           f"Authorize: {PORTAL_BASE_URL}?route=PENDING&v2=true")
    
    st.text_area("Email Payload Preview", sig, height=180, key=f"area_{i}_{sel_ic}_{rate}")

    if st.button("☁️ Sync & Generate Link", key=f"btn_{i}"):
        payload = {
            "icn": row['Name'], "wo": wo_title, "comp": pay, 
            "lCnt": cluster['unique_count'], "mi": mi, "time": t_str,
            "ic_home": row['Location'], "locs": " | ".join([t['addr'] for t in cluster['data']])
        }
        res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
        st.code(f"{PORTAL_BASE_URL}?route={res['routeId']}&v2=true")

# (Main Tab Logic follows)
