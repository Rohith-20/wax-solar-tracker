import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Real Weather", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 30   
REFRESH_RATE = 0.2      
MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. CLIMATE ENGINE (HIGH VARIANCE) ---
def get_climate_profile(date_obj):
    month = date_obj.month
    
    # 1. Base Seasonal Temps (Average)
    if month <= 2: base_temp = 28
    elif 3 <= month <= 5: base_temp = 38
    else: base_temp = 34
    
    # 2. Add Random "Day-to-Day" Noise (±3 degrees)
    daily_noise = np.random.uniform(-3, 3)
    
    # 3. WEATHER EVENTS (The "Jagged" Look)
    # Roll a dice (0 to 100)
    dice = np.random.randint(0, 100)
    
    if dice < 20: 
        # 20% Chance of Heavy Clouds (Big Drop)
        weather_factor = np.random.uniform(0.3, 0.5)
        temp_correction = -8
        condition = "Overcast"
    elif dice < 50:
        # 30% Chance of Partial Clouds (Small Drop)
        weather_factor = np.random.uniform(0.6, 0.8)
        temp_correction = -4
        condition = "Cloudy"
    elif dice > 90:
        # 10% Chance of Heat Spike (High Yield)
        weather_factor = 1.0
        temp_correction = +4
        condition = "Clear High"
    else:
        # Normal Sunny Day
        weather_factor = np.random.uniform(0.9, 0.98)
        temp_correction = 0
        condition = "Sunny"
        
    # Calculate Final Peak Temp for the day
    max_temp = int(base_temp + daily_noise + temp_correction)
    
    return max_temp, weather_factor, condition

# --- 3. INITIALIZATION (Fresh Start) ---
if 'solar_data_volatile' not in st.session_state:
    st.session_state.sim_time = datetime(2023, 1, 1, 6, 0)
    st.session_state.energy_today = 0.0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    
    # History DB
    st.session_state.solar_data_volatile = pd.DataFrame(columns=["Date", "Month", "Condition", "Peak_Temp_C", "Yield_Wh"])

# --- 4. PHYSICS ENGINE (LIVE) ---
def get_live_telemetry(current_time):
    # Get the volatile profile
    peak_temp_today, weather_factor_today, cond = get_climate_profile(current_time)
    
    hour = current_time.hour + (current_time.minute / 60)
    is_day = 6 <= hour <= 18
    
    if is_day:
        sun_angle = (hour - 12) * 15
        base_intensity = np.sin(((hour-6)/12) * np.pi)
        
        # Apply the Weather Factor directly to intensity
        real_intensity = base_intensity * weather_factor_today
        irradiance = int(max(0, real_intensity * 1000))
        
        # Temp varies heavily based on real intensity
        ambient = 25 + (real_intensity * (peak_temp_today - 25))
        wax = ambient + (real_intensity * 40)
        
        target_angle = -MAX_ROTATION + ((wax - 35)/40 * (MAX_ROTATION*2))
        panel_angle = np.clip(target_angle, -MAX_ROTATION, MAX_ROTATION)
        
        error = abs(sun_angle - panel_angle)
        efficiency = math.cos(math.radians(error))
        power = int(irradiance * (PANEL_CAPACITY/1000) * max(0, efficiency))
    else:
        power = 0
        ambient = 22.0
        wax = 22.0
        
    return {
        "str_time": current_time.strftime("%H:%M"),
        "power": power,
        "ambient": round(ambient, 1),
        "wax": round(wax, 1),
        "is_day": is_day,
        "condition": cond
    }

# --- 5. MAIN LOOP ---
if st.session_state.sim_time.month > 6:
    st.success("✅ Simulation Complete.")
    st.stop()

data = get_live_telemetry(st.session_state.sim_time)
step_wh = data['power'] * (MINUTES_PER_TICK / 60)
st.session_state.energy_today += step_wh

new_row = pd.DataFrame([{"Time": data['str_time'], "Watts": data['power']}])
st.session_state.live_power = pd.concat([st.session_state.live_power, new_row], ignore_index=True)

st.session_state.sim_time += timedelta(minutes=MINUTES_PER_TICK)

# New Day Logic
if st.session_state.sim_time.hour == 0 and st.session_state.sim_time.minute == 0:
    today_rec = pd.DataFrame([{
        "Date": (st.session_state.sim_time - timedelta(days=1)).strftime("%Y-%m-%d"),
        "Month": (st.session_state.sim_time - timedelta(days=1)).strftime("%b"),
        "Condition": data['condition'],
        "Peak_Temp_C": int(data['ambient']), # Logs the Peak Temp of that day
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.solar_data_volatile = pd.concat([st.session_state.solar_data_volatile, today_rec], ignore_index=True)
    st.session_state.energy_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])

# --- 6. UI ---
st.title("🌤️ Solar-X: Pilot Phase Monitor")
st.markdown(f"**Date:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Weather:** {data['condition']}")

tab1, tab2 = st.tabs(["🟢 Live View", "📅 2023 Analysis"])

with tab1:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Output Power", f"{data['power']} W", data['condition'])
    m2.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")
    m3.metric("Ambient Temp", f"{data['ambient']} °C")
    m4.metric("Wax Temp", f"{data['wax']} °C")
    
    st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")

with tab2:
    if 'solar_data_volatile' in st.session_state:
        df_hist = st.session_state.solar_data_volatile
        if not df_hist.empty:
            # 1. YIELD CHART (Blue Bars)
            st.write("**Daily Energy Yield (Wh)**")
            st.bar_chart(df_hist.set_index("Date")['Yield_Wh'], color="#0000FF")
            
            # 2. TEMP CHART (Red Lines - SHOWS VARIANCE)
            st.write("**Daily Peak Temperature (°C)**")
            st.line_chart(df_hist.set_index("Date")['Peak_Temp_C'], color="#FF0000")
            
            c1, c2 = st.columns([3, 1])
            with c1:
                st.dataframe(df_hist.sort_values(by="Date", ascending=False), use_container_width=True)
            with c2:
                total_kwh = df_hist['Yield_Wh'].sum() / 1000
                st.metric("Total Generation", f"{total_kwh:.2f} kWh")
        else:
            st.info("Gathering Day 1 Data...")

time.sleep(REFRESH_RATE)
st.rerun()
