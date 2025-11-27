import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Pilot Data", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 15   
REFRESH_RATE = 0.6      

MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. ASTRONOMICAL ENGINE (NEW LOGIC) ---
def get_sun_times(date_obj):
    """
    Returns (sunrise_hour, sunset_hour) based on the month.
    Simulates India/Chennai Latitude.
    """
    month = date_obj.month
    
    # Summer (May-Jul): Long Days
    if 5 <= month <= 7:
        sunrise = 5.75  # 5:45 AM
        sunset = 18.75  # 6:45 PM
    # Winter (Nov-Jan): Short Days
    elif month >= 11 or month <= 1:
        sunrise = 6.5   # 6:30 AM
        sunset = 17.75  # 5:45 PM
    # Moderate (Feb-Apr, Aug-Oct)
    else:
        sunrise = 6.0   # 6:00 AM
        sunset = 18.25  # 6:15 PM
        
    return sunrise, sunset

def generate_new_day_weather(date_obj):
    month = date_obj.month
    
    if month <= 2: base = 28
    elif 3 <= month <= 5: base = 38
    else: base = 32
    
    dice = np.random.randint(0, 100)
    
    if dice < 25: 
        condition = "Rainy" if dice < 10 else "Cloudy"
        factor = np.random.uniform(0.2, 0.6)
        peak_temp = base - np.random.randint(5, 10)
    elif dice > 85:
        condition = "Heatwave"
        factor = 1.0
        peak_temp = base + np.random.randint(3, 8)
    else:
        condition = "Sunny"
        factor = np.random.uniform(0.9, 0.98)
        peak_temp = base + np.random.randint(-2, 2)
        
    return {
        "condition": condition,
        "sun_factor": factor,
        "peak_temp": peak_temp
    }

# --- 3. INITIALIZATION (V7) ---
if 'sim_data_v7' not in st.session_state:
    st.session_state.sim_time = datetime(2023, 1, 1, 5, 0) # Start earlier (5 AM) to catch summer sunrise
    st.session_state.energy_today = 0.0
    st.session_state.max_temp_seen_today = 0.0 
    st.session_state.todays_weather = generate_new_day_weather(st.session_state.sim_time)
    
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.sim_data_v7 = pd.DataFrame(columns=["Date", "Condition", "Peak_Temp_C", "Yield_Wh"])

# --- 4. PHYSICS ENGINE ---
def get_live_telemetry(current_time, weather_profile):
    
    hour = current_time.hour + (current_time.minute / 60)
    
    # 1. Get Dynamic Sun Times
    sunrise, sunset = get_sun_times(current_time)
    
    # 2. Check Day Status
    is_day = sunrise <= hour <= sunset
    
    peak_temp_target = weather_profile['peak_temp']
    sun_factor = weather_profile['sun_factor']
    
    if is_day:
        # 3. Calculate Sun Progress (0.0 to 1.0) for the specific day length
        day_length = sunset - sunrise
        progress = (hour - sunrise) / day_length
        
        # 4. Sun Intensity (Sine Wave mapped to Progress)
        base_intensity = np.sin(progress * np.pi)
        
        # 5. Sun Angle (-90 to +90 mapped to Progress)
        sun_angle = (progress * 180) - 90
        
        real_intensity = base_intensity * sun_factor
        irradiance = int(max(0, real_intensity * 1000))
        
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
        
    return {
        "str_time": current_time.strftime("%H:%M"),
        "power": power,
        "irradiance": irradiance,
        "ambient": round(ambient, 1),
        "wax": round(wax, 1),
        "is_day": is_day,
        "sunrise": int(sunrise),   # For UI Display
        "sunset": int(sunset)      # For UI Display
    }

# --- 5. MAIN LOOP ---
if st.session_state.sim_time.month > 6:
    st.success("✅ Jan-Jun Simulation Complete.")
    st.stop()

# Get Data
data = get_live_telemetry(st.session_state.sim_time, st.session_state.todays_weather)

# Update Trackers
step_wh = data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.energy_today += step_wh

if data['ambient'] > st.session_state.max_temp_seen_today:
    st.session_state.max_temp_seen_today = data['ambient']

# Update Live Chart
new_row = pd.DataFrame([{"Time": data['str_time'], "Watts": data['power']}])
st.session_state.live_power = pd.concat([st.session_state.live_power, new_row], ignore_index=True)

# Advance Time
st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# New Day Logic
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    prev_date = st.session_state.sim_time - timedelta(days=1)
    
    new_record = pd.DataFrame([{
        "Date": prev_date.strftime("%Y-%m-%d"),
        "Condition": st.session_state.todays_weather['condition'],
        "Peak_Temp_C": int(st.session_state.max_temp_seen_today), 
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.sim_data_v7 = pd.concat([st.session_state.sim_data_v7, new_record], ignore_index=True)
    
    # Reset
    st.session_state.energy_today = 0
    st.session_state.max_temp_seen_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    st.session_state.todays_weather = generate_new_day_weather(st.session_state.sim_time)

# --- 6. DASHBOARD ---
curr_weather = st.session_state.todays_weather

st.title("🌤️ Solar-X: Pilot Phase Monitor")
# Updated Header with Dynamic Times
header_text = f"**Date:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Weather:** {curr_weather['condition']} | **Daylight:** {data['sunrise']}:00 - {data['sunset']}:00"
st.markdown(header_text)

tab1, tab2 = st.tabs(["🟢 Live View", "📅 2023 Analysis"])

with tab1:
    c1, c2, c3, c4, c5 = st.columns(5)
    
    c1.metric("Output Power", f"{data['power']} W", curr_weather['condition'])
    c2.metric("Irradiance", f"{data['irradiance']} W/m²")
    c3.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")
    c4.metric("Ambient Temp", f"{data['ambient']} °C")
    c5.metric("Wax Temp", f"{data['wax']} °C")
    
    st.divider()

    if data['is_day']:
        st.subheader("Real-Time Power Curve (Watts)")
        st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")
    else:
        st.info(f"🌙 System Standby: Sun is down. Next sunrise at {data['sunrise']}:00 AM.")

with tab2:
    df_hist = st.session_state.sim_data_v7
    
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
        st.info("Gathering Day 1 Data... (Simulation running at 1 min/day)")

time.sleep(REFRESH_RATE)
st.rerun()
