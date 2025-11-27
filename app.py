import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Pilot Data", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 30   
REFRESH_RATE = 0.3      
MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. CLIMATE ENGINE (2023 SIMULATOR) ---
def get_climate_profile(date_obj):
    month = date_obj.month
    
    # Logic for Jan - June 2023
    if month <= 2: # Jan-Feb (Winter)
        max_temp = np.random.randint(24, 28)
        weather_factor = np.random.uniform(0.8, 0.95)
        condition = "Sunny"
    elif 3 <= month <= 5: # Mar-May (Summer - Peak)
        max_temp = np.random.randint(35, 42)
        weather_factor = np.random.uniform(0.9, 1.0)
        condition = "Clear"
    else: # June (Pre-Monsoon)
        max_temp = np.random.randint(30, 35)
        weather_factor = np.random.uniform(0.6, 0.9)
        condition = "Cloudy"
        
    return max_temp, weather_factor, condition

# --- 3. INITIALIZATION (Clean Start) ---
# We use a new variable 'solar_data_2023' to ensure no old data conflicts
if 'solar_data_2023' not in st.session_state:
    st.session_state.sim_time = datetime.now().replace(hour=6, minute=0)
    st.session_state.energy_today = 0.0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    
    # GENERATE JAN 2023 - JUNE 2023 DATA
    history_data = []
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2023, 6, 30) # Only 6 months
    
    current_iter_date = start_date
    while current_iter_date <= end_date:
        peak_temp, sun_factor, cond = get_climate_profile(current_iter_date)
        ideal_yield = PANEL_CAPACITY * 6 
        actual_yield = int(ideal_yield * sun_factor)
        
        history_data.append({
            "Date": current_iter_date.strftime("%Y-%m-%d"),
            "Month": current_iter_date.strftime("%b"),
            "Condition": cond,
            "Peak_Temp_C": peak_temp,
            "Yield_Wh": actual_yield
        })
        current_iter_date += timedelta(days=1)
        
    st.session_state.solar_data_2023 = pd.DataFrame(history_data)

# --- 4. PHYSICS ENGINE (LIVE) ---
def get_live_telemetry(current_time):
    peak_temp_today, weather_factor_today, cond = get_climate_profile(current_time)
    
    hour = current_time.hour + (current_time.minute / 60)
    is_day = 6 <= hour <= 18
    
    if is_day:
        sun_angle = (hour - 12) * 15
        base_intensity = np.sin(((hour-6)/12) * np.pi)
        real_intensity = base_intensity * weather_factor_today
        irradiance = int(max(0, real_intensity * 1000))
        
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
        "Month": st.session_state.sim_time.strftime("%b"),
        "Condition": data['condition'],
        "Peak_Temp_C": int(data['ambient']),
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.solar_data_2023 = pd.concat([st.session_state.solar_data_2023, today_rec], ignore_index=True)
    st.session_state.energy_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])

# --- 6. DASHBOARD UI ---
st.title("🌤️ Solar-X: Pilot Phase Monitor")
st.markdown(f"**Live Simulation:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Condition:** {data['condition']}")

tab1, tab2 = st.tabs(["🟢 Live View", "📅 2023 Analysis (Jan-Jun)"])

with tab1:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Output Power", f"{data['power']} W", data['condition'])
    m2.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")
    m3.metric("Ambient Temp", f"{data['ambient']} °C")
    m4.metric("Wax Temp", f"{data['wax']} °C")
    
    st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")

with tab2:
    st.markdown("### 📊 H1 2023 Performance (Jan - June)")
    
    if 'solar_data_2023' in st.session_state:
        df_hist = st.session_state.solar_data_2023
        
        # SIMPLE BAR CHART (No complex Pivot Table to crash the app)
        st.write("**Daily Energy Yield (Wh)**")
        st.bar_chart(df_hist.set_index("Date")['Yield_Wh'], color="#0000FF")
        
        st.divider()
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.dataframe(
                df_hist.sort_values(by="Date", ascending=False),
                use_container_width=True,
                column_config={
                    "Yield_Wh": st.column_config.ProgressColumn("Energy", format="%d Wh", min_value=0, max_value=2000),
                }
            )
        with c2:
            total_kwh = df_hist['Yield_Wh'].sum() / 1000
            st.metric("Total Generation", f"{total_kwh:.2f} kWh")
            
            csv = df_hist.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download 2023 Data", csv, "solar_x_2023.csv", "text/csv")

time.sleep(REFRESH_RATE)
st.rerun()
