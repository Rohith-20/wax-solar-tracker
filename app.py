import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Pilot Data", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 15   
REFRESH_RATE = 0.5      # Smooth speed

MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. ROBUST WEATHER & TIME ENGINE ---
def generate_day_profile(date_obj):
    month = date_obj.month
    
    # --- A. STRICT SUNRISE/SUNSET LOGIC ---
    # Summer (March - August)
    if 3 <= month <= 8:
        # Sunrise: 5:45 AM (5.75) to 6:30 AM (6.5)
        sunrise = np.random.uniform(5.75, 6.5)
        # Sunset: 6:15 PM (18.25) to 6:40 PM (18.66)
        sunset = np.random.uniform(18.25, 18.66)
        season = "Summer"
        base_temp = 38
    
    # Winter (September - February)
    else:
        # Sunrise: 6:00 AM (6.0) to 6:30 AM (6.5)
        sunrise = np.random.uniform(6.0, 6.5)
        # Sunset: 6:00 PM (18.0) to 6:25 PM (18.41)
        sunset = np.random.uniform(18.0, 18.41)
        season = "Winter"
        base_temp = 29

    # --- B. WEATHER CONDITIONS ---
    dice = np.random.randint(0, 100)
    
    if dice < 20: 
        condition = "Rainy" if dice < 10 else "Cloudy"
        # Even in rain, we keep factor > 0.1 to avoid 0 irradiance mid-day
        factor = np.random.uniform(0.15, 0.4) 
        peak_temp = base_temp - np.random.randint(5, 10)
    elif dice > 90:
        condition = "Heatwave"
        factor = 1.0
        peak_temp = base_temp + np.random.randint(3, 8)
    else:
        condition = "Sunny"
        factor = np.random.uniform(0.85, 0.98)
        peak_temp = base_temp + np.random.randint(-2, 2)
        
    return {
        "condition": condition,
        "sun_factor": factor,
        "peak_temp": peak_temp,
        "sunrise": sunrise,
        "sunset": sunset,
        "season": season
    }

# --- 3. INITIALIZATION (Clean V10) ---
if 'sim_data_v10' not in st.session_state:
    # Start at 5:00 AM to catch the earliest sunrise
    st.session_state.sim_time = datetime(2023, 1, 1, 5, 0)
    st.session_state.energy_today = 0.0
    st.session_state.max_temp_seen_today = 0.0 
    
    st.session_state.todays_profile = generate_day_profile(st.session_state.sim_time)
    
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.sim_data_v10 = pd.DataFrame(columns=["Date", "Condition", "Peak_Temp_C", "Yield_Wh"])

# --- 4. PHYSICS ENGINE ---
def get_live_telemetry(current_time, day_profile):
    
    hour = current_time.hour + (current_time.minute / 60)
    
    sunrise = day_profile['sunrise']
    sunset = day_profile['sunset']
    
    # Check if sun is up
    is_day = sunrise <= hour <= sunset
    
    peak_temp_target = day_profile['peak_temp']
    sun_factor = day_profile['sun_factor']
    
    if is_day:
        # Calculate Sun Arc
        day_length = sunset - sunrise
        progress = (hour - sunrise) / day_length
        
        # Sine wave for intensity
        base_intensity = np.sin(progress * np.pi)
        
        # Geometry
        sun_angle = (progress * 180) - 90
        
        real_intensity = base_intensity * sun_factor
        
        # POWER FIX: Ensure mid-day doesn't drop to 0 unless it's NIGHT
        # If it's day, minimum intensity is 0.05 (Diffuse light)
        real_intensity = max(0.05, real_intensity)
        
        irradiance = int(real_intensity * 1000)
        
        # Thermodynamics
        ambient = 22 + (real_intensity * (peak_temp_target - 22))
        wax = ambient + (real_intensity * 40)
        
        target_angle = -MAX_ROTATION + ((wax - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
        error = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error))
        power = int(irradiance * (PANEL_CAPACITY/1000) * max(0, efficiency))
    else:
        power = 0
        irradiance = 0
        ambient = 22.0
        wax = 22.0
        
    # Format times strictly for display
    sunset_h = int(sunset)
    sunset_m = int((sunset % 1) * 60)
    
    return {
        "str_time": current_time.strftime("%H:%M"),
        "power": power,
        "irradiance": irradiance,
        "ambient": round(ambient, 1),
        "wax": round(wax, 1),
        "is_day": is_day,
        "sunset_display": f"{sunset_h:02d}:{sunset_m:02d}"
    }

# --- 5. MAIN LOOP ---
if st.session_state.sim_time.month > 6:
    st.success("✅ Jan-Jun Simulation Complete.")
    st.stop()

data = get_live_telemetry(st.session_state.sim_time, st.session_state.todays_profile)

step_wh = data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.energy_today += step_wh

if data['ambient'] > st.session_state.max_temp_seen_today:
    st.session_state.max_temp_seen_today = data['ambient']

new_row = pd.DataFrame([{"Time": data['str_time'], "Watts": data['power']}])
st.session_state.live_power = pd.concat([st.session_state.live_power, new_row], ignore_index=True)

st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# New Day Logic
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    prev_date = st.session_state.sim_time - timedelta(days=1)
    
    new_record = pd.DataFrame([{
        "Date": prev_date.strftime("%Y-%m-%d"),
        "Condition": st.session_state.todays_profile['condition'],
        "Peak_Temp_C": int(st.session_state.max_temp_seen_today), 
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.sim_data_v10 = pd.concat([st.session_state.sim_data_v10, new_record], ignore_index=True)
    
    # Reset
    st.session_state.energy_today = 0
    st.session_state.max_temp_seen_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.todays_profile = generate_day_profile(st.session_state.sim_time)

# --- 6. DASHBOARD ---
curr_profile = st.session_state.todays_profile

st.title("🌤️ Solar-X: Pilot Phase Monitor")

# Header
st.markdown(f"**Date:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Season:** {curr_profile['season']} | **Condition:** {curr_profile['condition']}")

# SIDEBAR DEBUG (To verify Sunset Time)
st.sidebar.markdown("### 🛠️ Daily Schedule")
st.sidebar.info(f"Scheduled Sunset: {data['sunset_display']}")

tab1, tab2 = st.tabs(["🟢 Live View", "📅 2023 Analysis"])

with tab1:
    c1, c2, c3, c4, c5 = st.columns(5)
    
    c1.metric("Output Power", f"{data['power']} W", curr_profile['condition'])
    c2.metric("Irradiance", f"{data['irradiance']} W/m²")
    c3.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")
    c4.metric("Ambient Temp", f"{data['ambient']} °C")
    c5.metric("Wax Temp", f"{data['wax']} °C")
    
    st.divider()

    # STRICT SYSTEM ACTIVE CHECK
    if data['irradiance'] > 0:
        st.subheader("Real-Time Power Curve (Watts)")
        st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")
    else:
        st.warning(f"🌙 SYSTEM INACTIVE: Night Mode (Irradiance: 0 W/m²)")

with tab2:
    df_hist = st.session_state.sim_data_v10
    
    if not df_hist.empty:
        total_gen_wh = df_hist['Yield_Wh'].sum()
        days_run = len(df_hist)
        
        kpi1, kpi2 = st.columns([1, 3])
        kpi1.metric("TOTAL ENERGY GAINED", f"{total_gen_wh/1000:.2f} kWh", f"Over {days_run} Days")
        kpi2.info("Accumulated energy yield since installation (Jan 1, 2023)")
        
        st.divider()

        st.subheader("Daily Energy Production (Wh)")
        st.bar_chart(df_hist.set_index("Date")['Yield_Wh'], color="#0000FF")
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(df_hist.sort_values(by="Date", ascending=False), use_container_width=True)
        with c2:
            st.download_button("📥 Download CSV", df_hist.to_csv(index=False).encode('utf-8'), "solar_x_2023.csv", "text/csv")
    else:
        st.info("Gathering Day 1 Data... (Simulation running)")

time.sleep(REFRESH_RATE)
st.rerun()
