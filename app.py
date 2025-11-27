import streamlit as st
import pandas as pd
import numpy as np
import time
import math
from datetime import datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Solar-X Climate Twin", page_icon="🌤️", layout="wide")

MINUTES_PER_TICK = 30   
REFRESH_RATE = 0.3      
MAX_ROTATION = 60
PANEL_CAPACITY = 250    # Watts

# --- 2. THE CLIMATE ENGINE (2022-2024 SIMULATOR) ---
# This function generates realistic weather based on the Month and Year
def get_climate_profile(date_obj):
    month = date_obj.month
    year = date_obj.year
    
    # Base Values
    max_temp = 30
    weather_factor = 1.0 # 1.0 = Perfect Sun, 0.2 = Heavy Rain
    condition = "Sunny"
    
    # SEASONAL LOGIC (Based on Tropical Climate like Chennai/India)
    
    # A. SUMMER (April - June): Extreme Heat, High Power
    if 4 <= month <= 6:
        max_temp = np.random.randint(38, 45) # Heatwave
        weather_factor = np.random.uniform(0.9, 1.0)
        condition = "Clear"
        
    # B. MONSOON (Oct - Dec): Cyclones, Rain, Low Power
    elif 10 <= month <= 12:
        max_temp = np.random.randint(25, 30)
        # Randomize rain events (30% chance of rain)
        if np.random.random() < 0.3:
            weather_factor = np.random.uniform(0.1, 0.4) # Dark clouds
            condition = "Rain/Overcast"
        else:
            weather_factor = np.random.uniform(0.6, 0.8) # Cloudy
            condition = "Cloudy"

    # C. WINTER (Jan - Feb): Cool, Clear Skies
    elif 1 <= month <= 2:
        max_temp = np.random.randint(24, 28)
        weather_factor = np.random.uniform(0.8, 0.95)
        condition = "Sunny"
        
    # D. REST OF YEAR: Moderate
    else:
        max_temp = np.random.randint(32, 36)
        weather_factor = np.random.uniform(0.7, 1.0)
        condition = "Partly Cloudy"
        
    return max_temp, weather_factor, condition

# --- 3. SESSION STATE INITIALIZATION ---
if 'sim_init' not in st.session_state:
    st.session_state.sim_time = datetime.now().replace(hour=6, minute=0)
    st.session_state.energy_today = 0.0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])
    
    # --- GENERATE 2022-2024 HISTORY DATABASE ---
    # We generate data from Jan 1, 2022 up to Yesterday
    history_data = []
    start_date = datetime(2022, 1, 1)
    end_date = datetime.now() - timedelta(days=1)
    
    # Loop through every single day (Fast Generation)
    current_iter_date = start_date
    while current_iter_date <= end_date:
        
        # Get Climate for that specific day
        peak_temp, sun_factor, cond = get_climate_profile(current_iter_date)
        
        # Calculate Energy Yield (Wh) for that day
        # Perfect day = 6 hours of peak sun * Capacity
        ideal_yield = PANEL_CAPACITY * 6 
        actual_yield = int(ideal_yield * sun_factor)
        
        history_data.append({
            "Date": current_iter_date.strftime("%Y-%m-%d"),
            "Year": current_iter_date.year,
            "Month": current_iter_date.strftime("%b"),
            "Condition": cond,
            "Peak_Temp_C": peak_temp,
            "Yield_Wh": actual_yield
        })
        current_iter_date += timedelta(days=1)
        
    st.session_state.history_db = pd.DataFrame(history_data)
    st.session_state.sim_init = True

# --- 4. PHYSICS ENGINE (LIVE) ---
def get_live_telemetry(current_time):
    # Use the same Climate Engine for "Live" accuracy
    peak_temp_today, weather_factor_today, cond = get_climate_profile(current_time)
    
    hour = current_time.hour + (current_time.minute / 60)
    is_day = 6 <= hour <= 18
    
    if is_day:
        # Sun Position
        sun_angle = (hour - 12) * 15
        
        # Intensity reduced by Weather Factor (Clouds/Rain)
        base_intensity = np.sin(((hour-6)/12) * np.pi)
        real_intensity = base_intensity * weather_factor_today
        irradiance = int(max(0, real_intensity * 1000))
        
        # Temps
        ambient = 25 + (real_intensity * (peak_temp_today - 25))
        wax = ambient + (real_intensity * 40)
        
        # Power
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
    # Save today to history
    today_rec = pd.DataFrame([{
        "Date": (st.session_state.sim_time - timedelta(days=1)).strftime("%Y-%m-%d"),
        "Year": st.session_state.sim_time.year,
        "Month": st.session_state.sim_time.strftime("%b"),
        "Condition": data['condition'],
        "Peak_Temp_C": int(data['ambient']),
        "Yield_Wh": int(st.session_state.energy_today)
    }])
    st.session_state.history_db = pd.concat([st.session_state.history_db, today_rec], ignore_index=True)
    st.session_state.energy_today = 0
    st.session_state.live_power = pd.DataFrame(columns=['Time', 'Watts'])

# --- 6. DASHBOARD UI ---
st.title("🌤️ Solar-X: Climate-Aware Tracking System")
st.markdown(f"**Current Simulation:** {st.session_state.sim_time.strftime('%Y-%m-%d')} | **Weather:** {data['condition']}")

tab1, tab2 = st.tabs(["🟢 Live Operations", "📅 Historical Analysis (2022-2024)"])

with tab1:
    # METRICS
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Output Power", f"{data['power']} W", data['condition'])
    m2.metric("Energy Today", f"{int(st.session_state.energy_today)} Wh")
    m3.metric("Ambient Temp", f"{data['ambient']} °C")
    m4.metric("Wax Temp", f"{data['wax']} °C")
    
    st.subheader("Real-Time Power Curve")
    st.area_chart(st.session_state.live_power.set_index("Time"), color="#FFA500")

with tab2:
    st.markdown("### 📊 Performance Analysis (2022 - 2024)")
    
    # DATA PREPARATION
    df_hist = st.session_state.history_db
    
    # 1. YEARLY COMPARISON CHART
    st.write("**Yearly Generation Trend**")
    # Group by Year and Month to show seasonality
    chart_data = df_hist.pivot_table(index='Month', columns='Year', values='Yield_Wh', aggfunc='mean')
    # Sort months correctly
    months_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    chart_data = chart_data.reindex(months_order)
    
    st.line_chart(chart_data)
    st.caption("Notice the dip in Oct-Nov (Monsoon Season) and Peak in May (Summer) across all years.")

    # 2. DETAILED DATA TABLE
    st.divider()
    c1, c2 = st.columns([3, 1])
    with c1:
        st.dataframe(
            df_hist.sort_values(by="Date", ascending=False),
            use_container_width=True,
            column_config={
                "Yield_Wh": st.column_config.ProgressColumn("Energy Yield", format="%d Wh", min_value=0, max_value=2000),
                "Condition": st.column_config.TextColumn("Weather")
            }
        )
    with c2:
        st.metric("Total Days Analyzed", len(df_hist))
        lifetime_mwh = df_hist['Yield_Wh'].sum() / 1000000
        st.metric("Lifetime Generation", f"{lifetime_mwh:.2f} MWh")
        
        csv = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Report", csv, "solar_x_2022_2024.csv", "text/csv")

time.sleep(REFRESH_RATE)
st.rerun()
