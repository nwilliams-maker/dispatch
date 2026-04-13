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

# Status Fills (For Cards)
TB_GREEN_FILL = "#dcfce7" # Ready
TB_BLUE_FILL = "#dbeafe"  # Sent
TB_RED_FILL = "#ffcccc"   # Flagged / Declined

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

# --- SECTION 2: UI STYLING ---
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

/* 1. GLOBAL APP SETTINGS */
.stApp {{ background-color: {TB_APP_BG} !important; color: #000000 !important; font-family: 'Inter', sans-serif !important; }}
.main .block-container {{ max-width: 1100px !important; padding-top: 2rem; }}
h1, h2, h3, h4, h5, h6 {{ font-weight: 800 !important; text-align: center !important; width: 100%; }}
label, div[data-testid="stWidgetLabel"] p {{ color: #000000 !important; font-weight: 600 !important; }}

/* 2. TOP-LEVEL POD NAVIGATION TABS */
.stTabs [data-baseweb="tab-list"] {{ 
    justify-content: center; gap: 12px; background: transparent !important; 
    padding: 15px 15px 20px 15px !important; border-bottom: 2px solid #cbd5e1 !important; margin-bottom: 15px !important; 
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: transparent !important; }}
.stTabs [data-baseweb="tab"] {{ 
    border-radius: 30px !important; margin: 0 5px !important; font-weight: 800 !important; 
    padding: 8px 25px !important; border: 2px solid transparent !important; 
}}
.stTabs [aria-selected="true"] {{ background-color: #ffffff !important; transform: translateY(-4px) !important; box-shadow: 0 10px 20px rgba(99, 48, 148, 0.25) !important; }}

/* Pod Color Assignments */
.stTabs [data-baseweb="tab"]:nth-of-type(1) {{ border-color: {TB_PURPLE} !important; color: #3b1d58 !important; background: white !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(2) {{ border-color: #3b82f6 !important; background-color: #f0f7ff !important; color: #1e3a8a !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(3) {{ border-color: #22c55e !important; background-color: #f0fdf4 !important; color: #064e3b !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(4) {{ border-color: #f97316 !important; background-color: #fffaf5 !important; color: #7c2d12 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(5) {{ border-color: #a855f7 !important; background-color: #faf5ff !important; color: #4c1d95 !important; }}
.stTabs [data-baseweb="tab"]:nth-of-type(6) {{ border-color: #ef4444 !important; background-color: #fef2f2 !important; color: #7f1d1d !important; }}

/* 3. EXPANDER & BUTTON HEIGHT MATCHING (THE 46px LOCK) */
div[data-testid="stExpander"] {{ 
    border: 1px solid #cbd5e1 !important; border-radius: 10px !important; 
    box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important; margin-bottom: 0px !important; 
    background-color: #ffffff !important; overflow: hidden !important; 
}}
div[data-testid="stExpander"] details summary {{ 
    height: 46px !important; min-height: 46px !important; padding: 0 10px !important; 
    display: flex !important; align-items: center !important; 
}}
div[data-testid="stExpander"] details summary p {{ margin: 0 !important; line-height: 46px !important; font-weight: 800 !important; color: #000000 !important; font-size: 0.95rem !important; }}

/* Revoke Button - Flush Alignment */
div[data-testid="stColumn"]:has(.flush-hook) button {{ 
    width: calc(100% + 1rem) !important; margin-left: -1rem !important; 
    border-top-left-radius: 0px !important; border-bottom-left-radius: 0px !important; 
    border-left: none !important; height: 46px !important; 
}}
div[data-testid="stColumn"]:has(.expander-hook) div[data-testid="stExpander"] {{ border-top-right-radius: 0px !important; border-bottom-right-radius: 0px !important; border-right: none !important; }}

/* Squashing row gaps */
div.element-container:has(div[data-testid="stExpander"]), 
div.element-container:has(div[data-testid="stHorizontalBlock"]:has(.expander-hook)) {{ 
    margin-bottom: -15px !important; 
}}

/* 4. COLUMN ALIGNMENT (FIX THE RIGHT COLUMN DROP) */
div.element-container:has(.dispatch-tabs-hook),
div.element-container:has(.awaiting-tabs-hook),
div.element-container:has(.expander-hook),
div.element-container:has(.flush-hook) {{ 
    position: absolute !important; visibility: hidden !important; height: 0px !important; margin: 0px !important; padding: 0px !important; 
}}

/* 5. NESTED TAB BYPASS: FORCE INDIVIDUAL ROUNDED PILLS */
div.element-container:has(.dispatch-tabs-hook) + div.element-container [data-baseweb="tab-list"],
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab-list"] {{ gap: 12px !important; background: transparent !important; }}

div.element-container:has(.dispatch-tabs-hook) + div.element-container [data-baseweb="tab"],
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab"] {{ 
    border-radius: 30px !important; border: 2px solid transparent !important; padding: 8px 18px !important; height: auto !important; min-height: 0 !important; 
}}
div.element-container:has(.dispatch-tabs-hook) + div.element-container [data-baseweb="tab-highlight"],
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab-highlight"] {{ display: none !important; }}

/* NESTED PILL COLORS & FILLS */
/* Left Column: Ready (Green) / Flagged (Light Red) */
div.element-container:has(.dispatch-tabs-hook) + div.element-container [data-baseweb="tab"]:nth-of-type(1) {{ border-color: #22c55e !important; color: #064e3b !important; background-color: #f0fdf4 !important; }}
div.element-container:has(.dispatch-tabs-hook) + div.element-container [data-baseweb="tab"]:nth-of-type(2) {{ border-color: #ef4444 !important; color: #7f1d1d !important; background-color: #fef2f2 !important; }}

/* Right Column: Sent (Blue) / Accepted (Light Green) / Declined (Light Red) */
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab"]:nth-of-type(1) {{ border-color: #3b82f6 !important; color: #1e3a8a !important; background-color: #f0f7ff !important; }}
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab"]:nth-of-type(2) {{ border-color: #22c55e !important; color: #064e3b !important; background-color: #f0fdf4 !important; }}
div.element-container:has(.awaiting-tabs-hook) + div.element-container [data-baseweb="tab"]:nth-of-type(3) {{ border-color: #ef4444 !important; color: #7f1d1d !important; background-color: #fef2f2 !important; }}

/* 6. HOVER & TRANSITIONS */
button:hover, .stTabs [data-baseweb="tab"]:hover {{ transform: translateY(-4px) !important; box-shadow: 0 12px 28px rgba(99, 48, 148, 0.35) !important; }}
div[data-testid="stExpander"]:hover {{ transform: translateY(-4px) !important; box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08) !important; }}
button:active, div[data-testid="stExpander"] details summary:active, .stTabs [data-baseweb="tab"]:active {{ transform: translateY(0px) scale(1) !important; box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important; }}
div[data-testid="stExpander"], .stTabs [data-baseweb="tab"], button {{ transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important; }}

/* 7. REFRESH & BUTTON BASICS */
div.refresh-btn-container > div > button {{ border: 1.2px solid {TB_PURPLE} !important; background-color: transparent !important; color: {TB_PURPLE} !important; font-weight: 700 !important; }}
button[kind="primary"] {{ background-color: {TB_GREEN} !important; color: white !important; height: 3.5rem !important; font-size: 1.2rem !important; font-weight: 800 !important; border: none !important; }}
button[kind="secondary"] {{ background-color: #ffffff !important; color: {TB_PURPLE} !important; border: 2px solid {TB_PURPLE} !important; font-weight: 800 !important; border-radius: 8px !important; }}

</style>
""", unsafe_allow_html=True)

# --- SECTION 3: LOGIC HANDLERS & UTILITIES ---

def background_sheet_move(cluster_hash, payload_json):
    """Safely moves records between sheets in a background thread to prevent UI lag."""
    try:
        requests.post(GAS_WEB_APP_URL, json={
            "action": "revokeRoute", 
            "cluster_hash": cluster_hash,
            "payload": payload_json
        })
    except Exception:
        pass

def instant_revoke_handler(cluster_hash, ic_name, payload_json):
    """Instantly updates local UI state and triggers the background move."""
    # 1. Update local session state for immediate visual feedback
    st.session_state[f"reverted_{cluster_hash}"] = True
    st.session_state[f"route_state_{cluster_hash}"] = "ready"
    
    # 2. Update History log for this route
    hist = st.session_state.get(f"history_{cluster_hash}", [])
    hist.append(f"{ic_name} ({datetime.now().strftime('%m/%d')} - Revoked)")
    st.session_state[f"history_{cluster_hash}"] = hist
    
    # 3. Visual Toast Notification
    st.toast(f"✅ Route for {ic_name} pulled back to Dispatch!")
    
    # 4. Trigger the Background Thread for the Google Sheet move
    threading.Thread(
        target=background_sheet_move, 
        args=(cluster_hash, payload_json)
    ).start()

def haversine(lat1, lon1, lat2, lon2):
    """Calculates the straight-line distance (miles) between two GPS points."""
    R = 3958.8 # Earth radius in miles
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def normalize_state(st_str):
    """Converts 'New York' or 'new york' to 'NY' using the STATE_MAP."""
    if not st_str: return "UNKNOWN"
    clean = str(st_str).strip().upper()
    return STATE_MAP.get(clean, clean)

# --- SECTION 4: DATA FETCHING ENGINES ---

@st.cache_data(ttl=15, show_spinner=False)
def fetch_sent_records_from_sheet():
    """Pulls current tracking data (Sent, Accepted, Declined) from Google Sheets."""
    try:
        base_url = f"{IC_SHEET_URL.split('/edit')[0]}/export?format=csv&gid="
        sheets_to_fetch = [
            (DECLINED_ROUTES_GID, "declined"),
            (ACCEPTED_ROUTES_GID, "accepted"),
            (SAVED_ROUTES_GID, "sent")
        ]
        
        sent_dict = {}
        ghost_routes = {"Blue": [], "Green": [], "Orange": [], "Purple": [], "Red": [], "UNKNOWN": []}
        
        for gid, status_label in sheets_to_fetch:
            try:
                df = pd.read_csv(base_url + gid)
                df.columns = [str(c).strip().lower() for c in df.columns]
                
                if 'json payload' in df.columns:
                    for _, row in df.iterrows():
                        try:
                            p = json.loads(row['json payload'])
                            tids = str(p.get('taskIds', '')).replace('|', ',').split(',')
                            c_name = str(row.get('contractor', 'Unknown Contractor'))
                            raw_ts = row.get('date created', '')
                            
                            ts_display = ""
                            if pd.notna(raw_ts) and str(raw_ts).strip():
                                try:
                                    ts_display = pd.to_datetime(raw_ts).strftime('%m/%d %I:%M %p')
                                except:
                                    ts_display = str(raw_ts)
                            
                            # 1. Map individual tasks to their current sheet status
                            for tid in tids:
                                tid = tid.strip()
                                if tid:
                                    sent_dict[tid] = {"name": c_name, "status": status_label, "time": ts_display}
                            
                            # 2. Capture 'Ghost' records for accepted routes that left the Onfleet pool
                            if status_label == 'accepted':
                                locs_str = str(p.get('locs', ''))
                                state_guess, city_guess = "UNKNOWN", "Unknown"
                                stops_list = [s.strip() for s in locs_str.split('|') if s.strip()]
                                
                                if len(stops_list) > 1:
                                    addr_parts = stops_list[1].split(',')
                                    if len(addr_parts) >= 2:
                                        state_guess = addr_parts[-1].strip().upper()
                                        city_guess = addr_parts[-2].strip()
                                
                                norm_state = normalize_state(state_guess)
                                pod_name = "UNKNOWN"
                                for p_name, p_config in POD_CONFIGS.items():
                                    if norm_state in p_config['states']:
                                        pod_name = p_name
                                        break
                                
                                if pod_name != "UNKNOWN":
                                    ghost_routes[pod_name].append({
                                        "contractor_name": c_name, "route_ts": ts_display,
                                        "city": city_guess, "state": norm_state,
                                        "stops": p.get('lCnt', 0), "tasks": p.get('tCnt', len(tids)),
                                        "pay": p.get('comp', 0)
                                    })
                        except: continue
            except: continue
        return sent_dict, ghost_routes
    except Exception as e:
        st.error(f"Failed to fetch portal records: {e}")
        return {}, {}

@st.cache_data(show_spinner=False)
def get_gmaps(home, waypoints):
    """Calculates mileage and drive time using Google Maps Directions API."""
    url = f"https://maps.googleapis.com/maps/api/directions/json?origin={home}&destination={home}&waypoints=optimize:true|{'|'.join(waypoints)}&key={GOOGLE_MAPS_KEY}"
    try:
        res = requests.get(url).json()
        if res['status'] == 'OK':
            mi = sum(l['distance']['value'] for l in res['routes'][0]['legs']) * 0.000621371
            hrs = sum(l['duration']['value'] for l in res['routes'][0]['legs']) / 3600
            return round(mi, 1), hrs, f"{int(hrs)}h {int((hrs * 60) % 60)}m"
    except: pass
    return 0, 0, "0h 0m"

def process_pod(pod_name, master_bar=None, pod_idx=0, total_pods=1):
    """The Core Routing Engine: Fetches tasks from Onfleet, clusters them, and checks viability."""
    config = POD_CONFIGS[pod_name]
    pod_weight = 1.0 / total_pods
    start_pct = pod_idx * pod_weight
    prog_bar = master_bar if master_bar else st.progress(0)
    
    def update_prog(rel_val, msg):
        global_val = min(start_pct + (rel_val * pod_weight), 0.99)
        prog_bar.progress(global_val, text=f"[{pod_name}] {msg}")

    try:
        update_prog(0.0, "📥 Extracting tasks...")
        # (Task fetching, clustering, and pricing logic goes here in the final assembly)
        # This function will be provided in full detail in the next 'Logic' section 
        # to ensure we don't hit character limits while maintaining meticulousness.
        pass 

    except Exception as e:
        st.error(f"Error initializing {pod_name}: {str(e)}")

# --- SECTION 5: THE CLUSTERING & ROUTING ENGINE ---

def process_pod(pod_name, master_bar=None, pod_idx=0, total_pods=1):
    config = POD_CONFIGS[pod_name]
    pod_weight = 1.0 / total_pods
    start_pct = pod_idx * pod_weight
    prog_bar = master_bar if master_bar else st.progress(0)
    
    def update_prog(rel_val, msg):
        global_val = min(start_pct + (rel_val * pod_weight), 0.99)
        prog_bar.progress(global_val, text=f"[{pod_name}] {msg}")

    try:
        update_prog(0.0, "📥 Extracting tasks from Onfleet...")
        APPROVED_TEAMS = [
            "a - escalation", "b - boosted campaigns", "b - local campaigns", 
            "c - priority nationals", "cvs kiosk removal", "n - national campaigns"
        ]

        # Fetch Team IDs from Onfleet
        teams_res = requests.get("https://onfleet.com/api/v2/teams", headers=headers).json()
        target_team_ids = [t['id'] for t in teams_res if any(appr in str(t.get('name', '')).lower() for appr in APPROVED_TEAMS)]
        esc_team_ids = [t['id'] for t in teams_res if 'escalation' in str(t.get('name', '')).lower()]

        all_tasks_raw = []
        url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}"
        
        while url:
            res = requests.get(url, headers=headers).json()
            all_tasks_raw.extend(res.get('tasks', []))
            url = f"https://onfleet.com/api/v2/tasks/all?state=0&from={int(time.time()*1000)-(80*24*3600*1000)}&lastId={res['lastId']}" if res.get('lastId') else None
            update_prog(min(len(all_tasks_raw)/500 * 0.4, 0.4), "📡 Fetching task pages...")

        # Filter tasks by Pod states and Escalation status
        pool = []
        for t in all_tasks_raw:
            container = t.get('container', {})
            if str(container.get('type', '')).upper() == 'TEAM' and container.get('team') not in target_team_ids: continue

            addr = t.get('destination', {}).get('address', {})
            stt = normalize_state(addr.get('state', ''))
            is_esc = (container.get('team') in esc_team_ids)
            
            if stt in config['states']:
                pool.append({
                    "id": t['id'], "city": addr.get('city', 'Unknown'), "state": stt,
                    "full": f"{addr.get('number','')} {addr.get('street','')}, {addr.get('city','')}, {stt}",
                    "lat": t['destination']['location'][1], "lon": t['destination']['location'][0],
                    "escalated": is_esc, "task_type": str(t.get('taskType', '')).strip()
                })
        
        clusters = []
        total_pool = len(pool)
        ic_df = st.session_state.get('ic_df', pd.DataFrame())
        v_ics_base = ic_df.dropna(subset=['Lat', 'Lng']).copy() if not ic_df.empty else pd.DataFrame()

        while pool:
            rel_prog = 0.4 + (0.6 * (1 - (len(pool) / total_pool if total_pool > 0 else 1)))
            update_prog(rel_prog, f"🗺️ Routing {len(pool)} remaining tasks...")
            
            anc = pool.pop(0)
            group = [anc]
            unique_stops = {anc['full']}
            rem = []

            # Cluster tasks within 50 miles, limited to 20 unique stops
            for t in pool:
                d = haversine(anc['lat'], anc['lon'], t['lat'], t['lon'])
                if d <= 50 and (len(unique_stops) < 20 or t['full'] in unique_stops):
                    group.append(t)
                    unique_stops.add(t['full'])
                else:
                    rem.append(t)
            
            # Distance and Price Check
            has_ic = False
            status = "Ready"
            if not v_ics_base.empty:
                v_ics_base['d'] = v_ics_base.apply(lambda x: haversine(anc['lat'], anc['lon'], x['Lat'], x['Lng']), axis=1)
                best_ic = v_ics_base.sort_values('d').iloc[0]
                if best_ic['d'] <= 60:
                    has_ic = True
                    _, hrs, _ = get_gmaps(best_ic['Location'], list(unique_stops)[:25])
                    est_pay = max(len(unique_stops) * 18.0, hrs * 25.0)
                    if (est_pay / len(unique_stops)) > 23.0: status = "Flagged"
                else:
                    status = "Flagged"
            else:
                status = "Flagged"

            pool = rem
            clusters.append({
                "data": group, "center": [anc['lat'], anc['lon']], 
                "stops": len(unique_stops), "city": anc['city'], "state": anc['state'],
                "status": status, "has_ic": has_ic,
                "esc_count": sum(1 for x in group if x.get('escalated'))
            })
            
        st.session_state[f"clusters_{pod_name}"] = clusters
        if not master_bar: prog_bar.empty()

    except Exception as e:
        st.error(f"Error initializing {pod_name}: {str(e)}")

# --- SECTION 6: THE UI RENDERING ENGINE ---

def render_dispatch(i, cluster, pod_name, is_sent=False, is_declined=False):
    """Renders the internal content of a route card, including pricing and Gmail logic."""
    task_ids = [str(t['id']).strip() for t in cluster['data']]
    cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
    sync_key = f"sync_{cluster_hash}"
    real_id = st.session_state.get(sync_key)
    link_id = real_id if real_id else "LINK_PENDING"

    # State keys for pricing synchronization
    pay_key = f"pay_val_{cluster_hash}"
    rate_key = f"rate_val_{cluster_hash}"
    sel_key = f"sel_{cluster_hash}"
    last_sel_key = f"last_sel_{cluster_hash}"

    st.write("### 🟢 Route Stops")

    # Display History Log if available
    hist = st.session_state.get(f"history_{cluster_hash}", [])
    if hist:
        st.markdown(f"<p style='color: #94a3b8; font-size: 13px; margin-top: -10px; margin-bottom: 15px; font-weight: 600;'>↩️ Previously sent to: {', '.join(hist)}</p>", unsafe_allow_html=True)

    # 1. STOP METRICS & PILLS
    stop_metrics = {}
    for c in cluster['data']:
        addr = c['full']
        if addr not in stop_metrics:
            stop_metrics[addr] = {'t_count': 0, 'n_ad': 0, 'inst': 0, 'oth': 0}
        stop_metrics[addr]['t_count'] += 1
        tt = str(c.get('task_type', '')).lower()
        if "install" in tt: stop_metrics[addr]['inst'] += 1
        elif any(x in tt for x in ["new ad", "digital"]): stop_metrics[addr]['n_ad'] += 1
        else: stop_metrics[addr]['oth'] += 1

    for addr, metrics in stop_metrics.items():
        pill = f"<span style='color: #633094; background-color: #f3e8ff; padding: 2px 6px; border-radius: 10px; font-weight: 800; font-size: 11px;'>{metrics['t_count']} Tasks</span>"
        st.markdown(f"**{addr}** &nbsp;{pill}", unsafe_allow_html=True)
        
    st.divider()

    # 2. CONTRACTOR SELECTION & DISTANCE
    ic_df = st.session_state.get('ic_df', pd.DataFrame())
    v_ics = ic_df.dropna(subset=['Lat', 'Lng']).copy()
    if not v_ics.empty:
        v_ics['d'] = v_ics.apply(lambda x: haversine(cluster['center'][0], cluster['center'][1], x['Lat'], x['Lng']), axis=1)
        v_ics = v_ics[v_ics['d'] <= 100].sort_values('d').head(5)

    if v_ics.empty:
        st.error("⚠️ No contractors found within 100 miles.")
        return

    ic_opts = {f"{r['Name']} ({round(r['d'],1)} mi)": r for _, r in v_ics.iterrows()}
    
    # 3. PRICING SYNC LOGIC
    def sync_on_total():
        val = st.session_state[pay_key]
        st.session_state[rate_key] = round(val / cluster['stops'], 2) if cluster['stops'] > 0 else 0

    def sync_on_rate():
        val = st.session_state[rate_key]
        st.session_state[pay_key] = round(val * cluster['stops'], 2)

    def update_for_new_contractor():
        selected_label = st.session_state[sel_key]
        if selected_label != st.session_state.get(last_sel_key):
            ic_new = ic_opts[selected_label]
            _, h, _ = get_gmaps(ic_new['Location'], list(stop_metrics.keys())[:25])
            new_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
            st.session_state[pay_key] = new_pay
            st.session_state[rate_key] = round(new_pay / cluster['stops'], 2)
            st.session_state[last_sel_key] = selected_label

    # Initial Pricing Setup
    if pay_key not in st.session_state:
        first_label = list(ic_opts.keys())[0]
        ic_init = ic_opts[first_label]
        _, h, _ = get_gmaps(ic_init['Location'], list(stop_metrics.keys())[:25])
        initial_pay = float(round(max(cluster['stops'] * 18.0, h * 25.0), 2))
        st.session_state[pay_key] = initial_pay
        st.session_state[rate_key] = round(initial_pay / cluster['stops'], 2)
        st.session_state[sel_key] = first_label

    # 4. PRICING UI ROW
    col_a, col_b, col_c, col_d = st.columns([1.5, 1, 1, 1])
    with col_a: st.selectbox("Contractor", list(ic_opts.keys()), key=sel_key, on_change=update_for_new_contractor)
    
    ic = ic_opts[st.session_state[sel_key]]
    mi, hrs, t_str = get_gmaps(ic['Location'], list(stop_metrics.keys())[:25])
    
    curr_rate = st.session_state[rate_key]
    needs_unlock = (curr_rate >= 25.0) or (ic['d'] > 60) or (cluster['status'] == 'Flagged')
    is_unlocked = st.checkbox("Authorize Premium Rate/Distance", key=f"lock_{cluster_hash}") if needs_unlock else True

    with col_b: st.number_input("Total Comp ($)", key=pay_key, on_change=sync_on_total, disabled=not is_unlocked)
    with col_c: st.number_input("Rate/Stop ($)", key=rate_key, on_change=sync_on_rate, disabled=not is_unlocked)
    with col_d: st.date_input("Deadline", datetime.now().date()+timedelta(14), key=f"dd_{cluster_hash}", disabled=not is_unlocked)

    # 5. FINANCIALS PREVIEW
    final_pay = st.session_state[pay_key]
    m1, m2 = st.columns(2)
    with m1: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px;'><p style='margin:0; font-size:24px; font-weight:800;'>Total: ${final_pay:,.2f}</p></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div style='background:#ffffff; border:1px solid #cbd5e1; border-radius:12px; padding:15px;'><p style='margin:0; font-size:24px; font-weight:800;'>{t_str}</p></div>", unsafe_allow_html=True)

    # 6. GMAIL LOGIC
    due = st.session_state.get(f"dd_{cluster_hash}", datetime.now().date()+timedelta(14))
    wo_val = f"{ic['Name']} - {datetime.now().strftime('%m%d%Y')}"
    
    email_body = (
        f"Hello {ic['Name']},\n\nWe have a new route available for review.\n\n"
        f"💰 Comp: ${final_pay:.2f}\n📅 Due: {due.strftime('%m/%d/%Y')}\n\n"
        f"Review & Respond Here:\n{PORTAL_BASE_URL}?route={link_id}&v2=true"
    )
    
    st.text_area("Email Preview", value=email_body, height=120, key=f"tx_{cluster_hash}", disabled=True)

    if st.button("🚀 GENERATE LINK & OPEN GMAIL", type="primary", key=f"gbtn_{cluster_hash}", disabled=not is_unlocked, use_container_width=True):
        with st.spinner("Saving..."):
            payload = {"icn": ic['Name'], "comp": final_pay, "taskIds": ",".join(task_ids)}
            res = requests.post(GAS_WEB_APP_URL, json={"action": "saveRoute", "payload": payload}).json()
            if res.get("success"):
                final_sig = email_body.replace("LINK_PENDING", res.get("routeId"))
                gmail_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={ic['Email']}&su=Route Request&body={requests.utils.quote(final_sig)}"
                st.components.v1.html(f"<script>window.open('{gmail_url}', '_blank');</script>", height=0)
                st.session_state[f"route_state_{cluster_hash}"] = "email_sent"
                st.rerun()

# --- SECTION 7: THE DASHBOARD LAYOUT ENGINE ---

def run_pod_tab(pod_name):
    """Organizes the metrics, map, and the two-column dispatch interface for a Pod."""
    st.markdown(f"<h2 style='color: {TB_PURPLE}; text-align:center;'>{pod_name} Pod Dashboard</h2>", unsafe_allow_html=True)

    # 1. INITIALIZE DATA
    if f"clusters_{pod_name}" not in st.session_state:
        if st.button(f"🚀 Initialize {pod_name} Data", key=f"init_{pod_name}"):
            process_pod(pod_name)
            st.rerun()
        return

    cls = st.session_state[f"clusters_{pod_name}"]
    if not cls:
        st.info(f"No tasks pending in the {pod_name} region.")
        return

    # Fetch live sheet status
    sent_db, ghost_db = fetch_sent_records_from_sheet()
    pod_ghosts = ghost_db.get(pod_name, [])

    # 2. CATEGORIZE ROUTES
    ready, review, sent, accepted, declined = [], [], [], [], []
    for c in cls:
        task_ids = [str(t['id']).strip() for t in c['data']]
        cluster_hash = hashlib.md5("".join(sorted(task_ids)).encode()).hexdigest()
        
        sheet_match = sent_db.get(next((tid for tid in task_ids if tid in sent_db), None))
        route_state = st.session_state.get(f"route_state_{cluster_hash}")
        is_reverted = st.session_state.get(f"reverted_{cluster_hash}", False)

        if sheet_match and not is_reverted:
            status = sheet_match.get('status')
            if status == 'declined': declined.append(c)
            elif status == 'accepted': accepted.append(c)
            else: sent.append(c)
        elif route_state == "email_sent" and not is_reverted:
            sent.append(c)
        else:
            if c['status'] == 'Ready': ready.append(c)
            else: review.append(c)

    # 3. METRICS & MAP (Simplified for Section 7)
    st.markdown(f"**Total Tasks:** {sum(len(c['data']) for c in cls)} | **Total Stops:** {sum(c['stops'] for c in cls)}")
    
    m = folium.Map(location=cls[0]['center'], zoom_start=6, tiles="cartodbpositron")
    for c in ready: folium.CircleMarker(c['center'], radius=7, color="#22c55e", fill=True).add_to(m)
    st_folium(m, height=350, use_container_width=True, key=f"map_{pod_name}")

    st.divider()

    # 4. SIDE-BY-SIDE INTERFACE
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("<h3 style='text-align:center;'>🚀 Dispatch</h3>", unsafe_allow_html=True)
        # HOOK: Tells CSS to style these specific tabs as pills
        st.markdown("<div class='dispatch-tabs-hook'></div>", unsafe_allow_html=True)
        t_ready, t_flagged = st.tabs(["📥 Ready", "⚠️ Flagged"])

        with t_ready:
            for i, c in enumerate(ready):
                with st.expander(f"🟢 {c['city']}, {c['state']} | {c['stops']} Stops"):
                    render_dispatch(i, c, pod_name)

        with t_flagged:
            for i, c in enumerate(review):
                with st.expander(f"🔴 {c['city']}, {c['state']} | {c['stops']} Stops"):
                    render_dispatch(i+100, c, pod_name)

    with col_right:
        st.markdown("<h3 style='text-align:center;'>⏳ Awaiting Confirmation</h3>", unsafe_allow_html=True)
        # HOOK: Tells CSS to style these specific tabs as pills
        st.markdown("<div class='awaiting-tabs-hook'></div>", unsafe_allow_html=True)
        t_sent, t_acc, t_dec = st.tabs(["✉️ Sent (Pending)", "✅ Accepted", "❌ Declined"])

        with t_sent:
            for i, c in enumerate(sent):
                exp_col, btn_col = st.columns([5, 1])
                with exp_col:
                    st.markdown("<div class='expander-hook'></div>", unsafe_allow_html=True)
                    with st.expander(f"✉️ Route Sent | {c['city']}, {c['state']}"):
                        render_dispatch(i+200, c, pod_name, is_sent=True)
                with btn_col:
                    st.markdown("<div class='flush-hook'></div>", unsafe_allow_html=True)
                    st.button("↩️ Revoke", key=f"rev_{i}_{pod_name}", use_container_width=True)

        with t_acc:
            for g in pod_ghosts:
                with st.expander(f"✅ {g['contractor_name']} | {g['city']}, {g['state']}"):
                    st.success(f"Route accepted for ${g['pay']}.")

        with t_dec:
            for i, c in enumerate(declined):
                with st.expander(f"❌ Route Declined | {c['city']}, {c['state']}"):
                    render_dispatch(i+300, c, pod_name, is_declined=True)

# --- SECTION 8: MAIN APP LOOP & ENTRY POINT ---

# 1. INITIALIZE GLOBAL STATE
if "ic_df" not in st.session_state:
    try:
        # Initial load of the IC Database
        st.session_state.ic_df = load_ic_database(IC_SHEET_URL)
    except Exception:
        st.error("Database connection failed. Please check your Sheet URL.")

# 2. APP HEADER (Title & Refresh)
col_title, col_ref = st.columns([10, 1])
with col_title:
    st.markdown(f"<h1 style='color: {TB_PURPLE}; text-align: left;'>Terraboost Media: Dispatch Command Center</h1>", unsafe_allow_html=True)

with col_ref:
    st.markdown("<div class='refresh-btn-container' style='margin-top: 25px;'>", unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="global_refresh"):
        st.cache_data.clear()
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# 3. INITIALIZE NAVIGATION TABS
# Tab 0 is Global, Tabs 1-5 are the Pods
tabs = st.tabs(["🌍 Global Overview", "🔵 Blue Pod", "🟢 Green Pod", "🟠 Orange Pod", "🟣 Purple Pod", "🔴 Red Pod"])

# --- TAB 0: GLOBAL OVERVIEW ---
with tabs[0]:
    st.markdown("<h2 style='text-align:center;'>🌍 Global Command Overview</h2>", unsafe_allow_html=True)
    
    # Global Initialization Button
    c_btn = st.columns([1, 2, 1])[1]
    if c_btn.button("🚀 Initialize All Pods", key="global_init_btn", use_container_width=True):
        st.session_state.trigger_pull = True

    st.divider()

    # Create the 5-column layout for Pod Summary Cards
    cols = st.columns(5)
    pod_names = ["Blue", "Green", "Orange", "Purple", "Red"]
    
    # Pre-fetch sheet data for the summary metrics
    current_sent_db, ghost_db = fetch_sent_records_from_sheet()

    for i, name in enumerate(pod_names):
        with cols[i]:
            has_data = f"clusters_{name}" in st.session_state
            
            # Dynamic border color based on pod name
            b_color = {"Blue": "#3b82f6", "Green": "#22c55e", "Orange": "#f97316", "Purple": "#a855f7", "Red": "#ef4444"}.get(name)
            
            if has_data:
                pod_cls = st.session_state[f"clusters_{name}"]
                pod_ghosts = ghost_db.get(name, [])
                
                # Simple math for the "Pill" summary
                total_routes = len(pod_cls) + len(pod_ghosts)
                
                st.markdown(f"""
                    <div style="border: 2px solid {b_color}; border-radius: 20px; padding: 15px; text-align: center; background: white;">
                        <h4 style="margin:0; color:{b_color};">{name} Pod</h4>
                        <p style="margin:5px 0 0 0; font-size:24px; font-weight:800;">{len(pod_cls)}</p>
                        <p style="margin:0; font-size:10px; text-transform:uppercase; opacity:0.6;">Active Routes</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="border: 2px solid #cbd5e1; border-radius: 20px; padding: 15px; text-align: center; background: #f8fafc; opacity:0.5;">
                        <h4 style="margin:0; color:#64748b;">{name} Pod</h4>
                        <p style="margin:10px 0; font-size:12px; font-weight:800;">OFFLINE</p>
                    </div>
                """, unsafe_allow_html=True)

    # Trigger the multi-pod data pull if requested
    if st.session_state.get("trigger_pull"):
        p_bar = st.progress(0, text="🎬 Initializing All Operational Data...")
        for idx, name in enumerate(pod_names):
            process_pod(name, master_bar=p_bar, pod_idx=idx, total_pods=len(pod_names))
        st.session_state.trigger_pull = False
        st.rerun()

# --- TABS 1-5: INDIVIDUAL PODS ---
# Loops through the pods and runs the layout engine for each
for i, name in enumerate(pod_names, 1):
    with tabs[i]:
        run_pod_tab(name)

