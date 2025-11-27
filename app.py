import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Power Monitor", page_icon="⚡", layout="wide")

# Simulation Speed
MINUTES_PER_TICK = 30  # Jump 30 mins per tick (Faster simulation)
REFRESH_RATE = 0.3     # Update speed

# Mechanical Constants
MAX_ROTATION = 60
PANEL_CAPACITY = 250   # Watts

# --- 2. SESSION STATE & "FAKE HISTORY" ---
# We generate fake history so the "Weekly" chart looks good immediately
if 'sim_init' not in st.session_state:
    # Start at 6:00 AM Today
    st.session_state.sim_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    st.session_state.total_energy_today = 0.0
    
    # Create a "Live" dataframe for the Area Chart (Power)
    st.session_state.live_power_data = pd.DataFrame(columns=['Time', 'Power_Watts'])
    
    # Create "Past Week" history for the Bar Chart
    # Simulating 7 days of random previous generation (4kWh to 6kWh range)
    past_days = []
    for i in range(7, 0, -1):
        date_label = (datetime.now() - timedelta(days=i)).strftime("%a") # Mon, Tue...
        energy_val = np.random.uniform(4000, 6500) # Random Wh
        past_days.append({"Day": date_label, "Energy_Wh": int(energy_val)})
    
    st.session_state.daily_history = pd.DataFrame(past_days)
    st.session_state.sim_init = True

# --- 3. PHYSICS ENGINE ---
def get_live_physics(current_time):
    hour = current_time.hour + (current_time.minute / 60)
    is_daytime = 6 <= hour <= 18
    
    if is_daytime:
        # Physics Model
        sun_angle = (hour - 12) * 15
        sun_intensity = np.sin(((hour-6)/12) * np.pi)
        irradiance = int(max(0, sun_intensity * 1000))
        
        # Temps
        ambient_temp = 25 + (sun_intensity * 10) # 25-35C
        wax_temp = ambient_temp + (sun_intensity * 45) # Hotter
        
        # Angle
        target_angle = -MAX_ROTATION + ((wax_temp - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
        # Power Calculation (Cosine Loss)
        error_deg = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error_deg))
        power = int(irradiance * (PANEL_CAPACITY / 1000) * max(0, efficiency))
    else:
        # Night
        irradiance = 0
        ambient_temp = 22.0
        wax_temp = 22.0
        panel_angle = -60
        power = 0
        
    return {
        "time_obj": current_time,
        "time_str": current_time.strftime("%H:%M"),
        "ambient": round(ambient_temp, 1),
        "wax_temp": round(wax_temp, 1),
        "power": power,
        "is_day": is_daytime
    }

# --- 4. MAIN LOOP ---
live_data = get_live_physics(st.session_state.sim_time)

# Update Energy (Accumulation)
step_energy = live_data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.total_energy_today += step_energy

# Update Charts
# 1. Live Power Chart (Last 50 ticks)
new_power_row = pd.DataFrame([{"Time": live_data['time_str'], "Power_Watts": live_data['power']}])
st.session_state.live_power_data = pd.concat([st.session_state.live_power_data, new_power_row], ignore_index=True)
if len(st.session_state.live_power_data) > 50:
    st.session_state.live_power_data = st.session_state.live_power_data.iloc[1:]

# Time Advance
st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# New Day Logic
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    # Save today's total to history
    today_label = st.session_state.sim_time.strftime("%a")
    new_day_row = pd.DataFrame([{"Day": "Today", "Energy_Wh": int(st.session_state.total_energy_today)}])
    
    # Append to bar chart history
    st.session_state.daily_history = pd.concat([st.session_state.daily_history, new_day_row], ignore_index=True)
    
    # Reset for tomorrow
    st.session_state.total_energy_today = 0
    st.session_state.live_power_data = pd.DataFrame(columns=['Time', 'Power_Watts']) # Clear live chart

# --- 5. DASHBOARD UI (TRADING STYLE) ---

st.title("⚡ Solar-X: Generation Dashboard")
st.markdown("### 🟢 Live Site Performance")

# A. METRICS ROW (Added Ambient Temp Here)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

kpi1.metric("⚡ Live Power Output", f"{live_data['power']} W", delta="Active" if live_data['power']>0 else "Idle")
kpi2.metric("🔋 Energy Today", f"{int(st.session_state.total_energy_today)} Wh", "Accumulating...")
# SEPARATED AMBIENT TEMP AS REQUESTED
kpi3.metric("🌡 Ambient Temp", f"{live_data['ambient']} °C", "Air")
kpi4.metric("🌡 Wax Actuator", f"{live_data['wax_temp']} °C", f"{live_data['wax_temp']-live_data['ambient']:.1f} ΔT")

# B. CHARTS ROW
c1, c2 = st.columns([2, 1])

with c1:
    st.subheader("📈 Live Power Curve (Watts)")
    # Area Chart looks like a Trading Chart
    st.area_chart(st.session_state.live_power_data.set_index("Time"), color="#00ff00")
    st.caption("Real-time power generation profile (30-min intervals)")

with c2:
    st.subheader("📊 Weekly Yield (Wh)")
    # Bar Chart for Daily/Weekly History
    # We combine Past History + Current Day for the chart
    current_day_df = pd.DataFrame([{"Day": "Today", "Energy_Wh": int(st.session_state.total_energy_today)}])
    full_history = pd.concat([st.session_state.daily_history, current_day_df], ignore_index=True)
    
    st.bar_chart(full_history.set_index("Day"), color="#FF4B4B")
    st.caption("Daily Energy Harvested (Last 7 Days + Today)")

# C. STATUS FOOTER
if live_data['is_day']:
    st.success(f"✅ SYSTEM OPTIMAL | Time: {live_data['time_str']} | Tracking Sun Position")
else:
    st.info(f"🌙 NIGHT MODE | Time: {live_data['time_str']} | System Retracted")

# Refresh
time.sleep(REFRESH_RATE)
st.rerun()
