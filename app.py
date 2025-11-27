import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Live Monitor", page_icon="📡", layout="wide")

# Simulation Settings
# 1 "Tick" in simulation = 15 minutes of real time
MINUTES_PER_TICK = 15 
# How fast the app updates (in seconds)
REFRESH_RATE = 0.5 

# Mechanical Constants
MAX_ROTATION = 60        # ±60 degrees
PANEL_CAPACITY = 250     # Watts

# --- 2. SESSION STATE INITIALIZATION (The "Memory") ---
if 'sim_time' not in st.session_state:
    # Start simulation at 5:00 AM on Day 1
    st.session_state.sim_time = datetime(2025, 1, 1, 5, 0, 0)
    st.session_state.total_energy = 0.0
    st.session_state.data_history = pd.DataFrame(columns=['Time', 'Sun_Angle', 'Panel_Angle', 'Power'])
    st.session_state.day_count = 1

# --- 3. PHYSICS ENGINE (Continuous) ---

def get_live_physics(current_time):
    """
    Generates a single data point based on the exact time of day.
    Handles Day/Night transitions automatically.
    """
    hour = current_time.hour + (current_time.minute / 60)
    
    # A. Sun Position (Simple 6am-6pm model)
    # If it's night (before 6 or after 18), sun is "down"
    is_daytime = 6 <= hour <= 18
    
    if is_daytime:
        # Map 6am-6pm to -90 to +90 degrees
        sun_angle = (hour - 12) * 15
        # Sine wave intensity for light
        sun_intensity = np.sin(((hour-6)/12) * np.pi)
        irradiance = int(max(0, sun_intensity * 1000))
        
        # Temps rise during day
        ambient_temp = 25 + (sun_intensity * 10)
        # Wax heats up (Greenhouse effect)
        wax_temp = ambient_temp + (sun_intensity * 45)
        
        # Panel Angle (Wax Expansion)
        target_angle = -MAX_ROTATION + ((wax_temp - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
    else:
        # NIGHT TIME LOGIC
        sun_angle = -90 # Sun is gone
        irradiance = 0
        
        # Temps cool down
        ambient_temp = 20
        wax_temp = 20 # Wax matches ambient at night
        
        # Panel Retracts (Spring return)
        # At night, panel sits at -60 (East) waiting for morning
        panel_angle = -60 

    # B. Power Calculation
    if is_daytime:
        error_deg = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error_deg))
        efficiency = max(0, efficiency)
        power = int(irradiance * (PANEL_CAPACITY / 1000) * efficiency)
    else:
        power = 0
        
    return {
        "datetime": current_time,
        "time_str": current_time.strftime("%H:%M"),
        "is_day": is_daytime,
        "sun_angle": int(sun_angle),
        "panel_angle": int(panel_angle),
        "ambient": round(ambient_temp, 1),
        "wax_temp": round(wax_temp, 1),
        "irradiance": irradiance,
        "power": power
    }

# --- 4. MAIN LOOP LOGIC ---

# 1. Calculate ONE step of physics
live_data = get_live_physics(st.session_state.sim_time)

# 2. Update Total Energy (Wh)
# Power (W) * Hours (0.25 hours per tick)
step_energy = live_data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.total_energy += step_energy

# 3. Update History (For Charts)
new_row = pd.DataFrame([{
    'Time': live_data['datetime'], # Keep full datetime for sorting
    'Sun_Angle': live_data['sun_angle'],
    'Panel_Angle': live_data['panel_angle'],
    'Power': live_data['power']
}])

# Add to history and keep only last 100 points (Rolling Window)
st.session_state.data_history = pd.concat([st.session_state.data_history, new_row], ignore_index=True)
if len(st.session_state.data_history) > 100:
    st.session_state.data_history = st.session_state.data_history.iloc[1:]

# 4. Advance Time
st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# Check for new day
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    st.session_state.day_count += 1

# --- 5. DASHBOARD UI ---

st.title("📡 Solar-X: Continuous Live Telemetry")
st.markdown(f"**Status:** System Online | **Day:** {st.session_state.day_count} | **Time:** {live_data['time_str']}")

# Status Banner
if live_data['is_day']:
    st.success(f"☀️ **DAYTIME MODE** - Tracking Active")
else:
    st.info(f"🌙 **NIGHT MODE** - System Retracting/Idle")

# Metrics
col1, col2, col3, col4 = st.columns(4)
col1.metric("⚡ Current Power", f"{live_data['power']} W")
col2.metric("🔋 Total Harvested", f"{int(st.session_state.total_energy/1000)} kWh", f"+{int(step_energy)} Wh")
col3.metric("🌡 Wax Temp", f"{live_data['wax_temp']} °C", f"{live_data['ambient']}° Amb")
col4.metric("☀ Irradiance", f"{live_data['irradiance']} W/m²")

# Visualization Split
c_chart, c_cam = st.columns([2, 1])

with c_cam:
    st.write("**Live Angle Feed**")
    # Dynamic image caption
    img_caption = f"Panel: {live_data['panel_angle']}° | Sun: {live_data['sun_angle']}°"
    
    # Use a Dark image for night, Bright for day
    if live_data['is_day']:
        st.image("https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=600", caption=img_caption)
    else:
        # Night sky image
        st.image("https://images.unsplash.com/photo-1504608524841-42fe6f032b4b?q=80&w=600", caption=img_caption + " (Night)")

with c_chart:
    st.write("**Performance Trend (Last 24 Hours)**")
    # Clean chart data
    chart_df = st.session_state.data_history.copy()
    chart_df = chart_df.set_index("Time")
    
    # Show two separate charts or one combined? Combined is better.
    st.line_chart(chart_df[['Sun_Angle', 'Panel_Angle']], color=["#FDB813", "#0072CE"])

# --- 6. AUTO-REFRESH (The Infinite Loop) ---
time.sleep(REFRESH_RATE)
st.rerun()
