import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Enterprise Monitor", page_icon="🏢", layout="wide")

# Simulation Speed
MINUTES_PER_TICK = 30   # 30 mins per refresh
REFRESH_RATE = 0.3      # Speed of animation

# Mechanical Constants
MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. SESSION STATE & DATABASE SIMULATION (FIXED) ---
# We now check for the specific variable 'energy_today' to prevent crashing
if 'energy_today' not in st.session_state:
    # A. Initialize Time
    st.session_state.sim_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    st.session_state.energy_today = 0.0
    
    # B. Live Chart Data (Empty start)
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    
    # C. HISTORY DATABASE (Simulating last 30 days of storage)
    history_data = []
    current_date = datetime.now()
    for i in range(30, 0, -1):
        # Generate realistic past data
        past_date = current_date - timedelta(days=i)
        
        # Randomize weather: Sunny (6kWh) vs Cloudy (2kWh)
        weather_factor = np.random.uniform(0.3, 1.0) 
        daily_yield = int(PANEL_CAPACITY * 6 * weather_factor) # Approx Wh calculation
        
        history_data.append({
            "Date": past_date.strftime("%Y-%m-%d"),
            "Status": "Optimal" if weather_factor > 0.7 else "Low Output",
            "Peak_Temp_C": np.random.randint(45, 70),
            "Total_Energy_Wh": daily_yield
        })
        
    st.session_state.history_db = pd.DataFrame(history_data)

# --- 3. PHYSICS ENGINE ---
def get_live_telemetry(current_time):
    hour = current_time.hour + (current_time.minute / 60)
    is_day = 6 <= hour <= 18
    
    if is_day:
        # Physics
        sun_angle = (hour - 12) * 15
        intensity = np.sin(((hour-6)/12) * np.pi)
        irradiance = int(max(0, intensity * 1000))
        
        # Temps
        ambient = 25 + (intensity * 10)
        wax = ambient + (intensity * 45)
        
        # Power
        target_angle = -MAX_ROTATION + ((wax - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
        error = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error))
        power = int(irradiance * (PANEL_CAPACITY/1000) * max(0, efficiency))
    else:
        # Night
        power = 0
        ambient = 22.0
        wax = 22.0
        
    return {
        "str_time": current_time.strftime("%H:%M"),
        "power": power,
        "ambient": round(ambient, 1),
        "wax": round(wax, 1),
        "is_day": is_day
    }

# --- 4. MAIN LOOP ---
data = get_live_telemetry(st.session_state.sim_time)

# Accumulate Energy
step_wh = data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.energy_today += step_wh

# Update Live Chart
new_row = pd.DataFrame([{"Time": data['str_time'], "Watts": data['power']}])
st.session_state.live_power = pd.concat([st.session_state.live_power, new_row], ignore_index=True)

# Advance Time
st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# New Day Logic (Save to History DB)
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    # Create record
    yesterday_record = pd.DataFrame([{
        "Date": (st.session_state.sim_time - timedelta(days=1)).strftime("%Y-%m-%d"),
        "Status": "Optimal",
        "Peak_Temp_C": 65, # Simulated peak
        "Total_Energy_Wh": int(st.session_state.energy_today)
    }])
    # Append to DB
    st.session_state.history_db = pd.concat([st.session_state.history_db, yesterday_record], ignore_index=True)
    # Reset
    st.session_state.energy_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])

# --- 5. UI LAYOUT (TABS) ---
st.title("⚡ Solar-X: Enterprise Monitor")

# CREATE TABS HERE
tab1, tab2 = st.tabs(["📈 Live Dashboard", "🗃️ Historical Reports"])

with tab1:
    # --- LIVE VIEW ---
    st.markdown("### 🟢 Real-Time Operations")
    
    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("⚡ Output", f"{data['power']} W", delta="Generating" if data['power'] > 0 else "Idle")
    m2.metric("🔋 Energy Today", f"{int(st.session_state.energy_today)} Wh")
    m3.metric("🌡 Ambient Air", f"{data['ambient']} °C")
    m4.metric("🌡 Wax Cylinder", f"{data['wax']} °C", f"{data['wax'] - data['ambient']:.1f} ΔT")
    
    st.divider()
    
    # SINGLE CHART (Watts per Hour)
    st.subheader("Live Power Curve (Watts/Hour)")
    # Using Area chart for that "Trading" look
    st.area_chart(st.session_state.live_power.set_index("Time"), color="#00FF00")
    
    if data['is_day']:
        st.success(f"✅ SYSTEM ACTIVE | Time: {data['str_time']}")
    else:
        st.info(f"🌙 NIGHT MODE | Time: {data['str_time']}")

with tab2:
    # --- HISTORY VIEW ---
    st.markdown("### 🗃️ System Data Logs")
    
    c1, c2 = st.columns([3, 1])
    
    with c1:
        st.write(" **Daily Yield Database (Last 30 Days)**")
        # Show the DataFrame as a clean interactive table
        st.dataframe(
            st.session_state.history_db.sort_values(by="Date", ascending=False),
            use_container_width=True,
            column_config={
                "Date": "Date",
                "Total_Energy_Wh": st.column_config.NumberColumn("Yield (Wh)", format="%d Wh"),
                "Peak_Temp_C": "Max Wax Temp (°C)",
                "Status": "System Health"
            }
        )
    
    with c2:
        st.write(" **Export Data**")
        st.write("Download full logs for sustenance engineering analysis.")
        
        # Convert DF to CSV for download
        csv = st.session_state.history_db.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name='solar_x_history.csv',
            mime='text/csv',
        )
        
        st.divider()
        st.metric("Total Days Logged", len(st.session_state.history_db))
        total_lifetime = st.session_state.history_db['Total_Energy_Wh'].sum() / 1000
        st.metric("Lifetime Generation", f"{total_lifetime:.1f} kWh")

# Refresh Loop
time.sleep(REFRESH_RATE)
st.rerun()
