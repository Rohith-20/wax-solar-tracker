import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Pilot Data", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 15   
REFRESH_RATE = 0.5      

MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. ROBUST WEATHER & TIME ENGINE ---
def generate_day_profile(date_obj):
    month = date_obj.month
    
    # Summer (March - August)
    if 3 <= month <= 8:
        sunrise = np.random.uniform(5.75, 6.5)
        sunset = np.random.uniform(18.25, 18.66)
        base_temp = 38
    # Winter (September - February)
    else:
        sunrise = np.random.uniform(6.0, 6.5)
        sunset = np.random.uniform(18.0, 18.41)
        base_temp = 29

    dice = np.random.randint(0, 100)
    
    if dice < 20: 
        condition = "Rainy" if dice < 10 else "Cloudy"
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
        "sunset": sunset
    }

# --- 3. INITIALIZATION (Clean V13) ---
if 'sim_data_v13' not in st.session_state:
    st.session_state.sim_time = datetime(2023, 1, 1, 5, 0)
    st.session_state.energy_today = 0.0
    st.session_state.max_temp_seen_today = 0.0 
    
    st.session_state.todays_profile = generate_day_profile(st.session_state.sim_time)
    
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.sim_data_v13 = pd.DataFrame(columns=["Date", "Condition", "Peak_Temp_C", "Yield_Wh"])

# --- 4. PHYSICS ENGINE ---
def get_live_telemetry(current_time, day_profile):
    
    hour = current_time.hour + (current_time.minute / 60)
    
    sunrise = day_profile['sunrise']
    sunset = day_profile['sunset']
    is_day = sunrise <= hour <= sunset
    
    peak_temp_target = day_profile['peak_temp']
    sun_factor = day_profile['sun_factor']
    
    # Default Health Values
    health_status = "Standby" 
    health_score = 100.0
    
    if is_day:
        day_length = sunset - sunrise
        progress = (hour - sunrise) / day_length
        
        base_intensity = np.sin(progress * np.pi)
        sun_angle = (progress * 180) - 90
        
        real_intensity = base_intensity * sun_factor
        real_intensity = max(0.05, real_intensity)
        irradiance = int(real_intensity * 1000)
        
        ambient = 22 + (real_intensity * (peak_temp_target - 22))
        wax = ambient + (real_intensity * 40)
        
        target_angle = -MAX_ROTATION + ((wax - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
        error = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error))
        power = int(irradiance * (PANEL_CAPACITY/1000) * max(0, efficiency))
        
        # --- HEALTH LOGIC (MPU-6050 Simulation) ---
        # 1. We simulate the sensor reading (with slight vibration noise)
        sensor_reading_angle = panel_angle + np.random.uniform(-1.0, 1.0)
        
        # 2. Compare Math Model vs Sensor Reading
        deviation = abs(panel_angle - sensor_reading_angle)
        
        # 3. Determine Health
        if deviation < 2.0:
            health_status = "Optimal"
            health_score = 100.0 - (deviation * 0.5)
        elif deviation < 5.0:
            health_status = "Vibration"
            health_score = 95.0
        else:
            health_status = "Jam Detected"
            health_score = 50.0
            
    else:
        power = 0
        irradiance = 0
        ambient = 22.0
        wax = 22.0
        health_status = "Sleep Mode"
        health_score = 100.0
        
    return {
        "str_time": current_time.strftime("%H:%M"),
        "power": power,
        "irradiance": irradiance,
        "ambient": round(ambient, 1),
        "wax": round(wax, 1),
        "is_day": is_day,
        "health_status": health_status,
        "health_score": round(health_score, 1)
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

if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    prev_date = st.session_state.sim_time - timedelta(days=1)
    new_record = pd.DataFrame([{
        "Date": prev_date.strftime("%Y-%m-%d"),
        "Condition": st.session_state.todays_profile['condition'],
        "Peak_Temp_C": int(st.session_state.max_temp_seen_today), 
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.sim_data_v13 = pd.concat([st.session_state.sim_data_v13, new_record], ignore_index=True)
    
    st.session_state.energy_today = 0
    st.session_state.max_temp_seen_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.todays_profile = generate_day_profile(st.session_state.sim_time)

# --- 6. DASHBOARD UI ---
curr_profile = st.session_state.todays_profile

st.title("🌤️ Solar-X: Pilot Phase Monitor")
st.markdown(f"**Date:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Condition:** {curr_profile['condition']}")

tab1, tab2 = st.tabs(["🟢 Live View", "📅 2023 Analysis"])

with tab1:
    # --- ROW 1: ENERGY (3 Cards) ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Output Power", f"{data['power']} W", curr_profile['condition'])
    c2.metric("Irradiance", f"{data['irradiance']} W/m²")
    c3.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")

    # --- ROW 2: DIAGNOSTICS (3 Cards) ---
    c4, c5, c6 = st.columns(3)
    # Combined Temp Card logic to avoid visual clutter if preferred, but distinct is better for engineering
    c4.metric("Ambient Temp", f"{data['ambient']} °C")
    c5.metric("Wax Temp", f"{data['wax']} °C", f"{data['wax']-data['ambient']:.1f} ΔT")
    c6.metric("Mechanism Health", f"{data['health_status']}", f"{data['health_score']}% Score")
    
    st.divider()

    if data['irradiance'] > 0:
        st.subheader("Real-Time Power Curve (Watts)")
        st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")
    else:
        st.warning(f"🌙 SYSTEM INACTIVE: Night Mode (Irradiance: 0 W/m²)")

with tab2:
    df_hist = st.session_state.sim_data_v13
    
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
