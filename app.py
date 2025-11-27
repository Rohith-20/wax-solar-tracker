import streamlit as st
import pandas as pd
import numpy as np
import time

# --- 1. CONFIGURATION & CONSTANTS ---
st.set_page_config(page_title="Wax Solar Tracker AI", layout="wide")

# Mechanical Constants
MELTING_POINT = 25       # Degrees C
MAX_EXTENSION = 50       # mm
DEG_PER_MM = 1.2         # Linkage geometry
PANEL_CAPACITY = 100     # Watts (Size of your panel)

# --- 2. AI LOGIC MODULE (The Brain) ---
def calculate_expected_angle(wax_temp, ambient_temp):
    """
    Predicts panel angle based on differential heating.
    Wax only expands if it is significantly hotter than ambient.
    """
    effective_temp_diff = wax_temp - ambient_temp
    
    # Wax starts working when it's 10 degrees above ambient
    if effective_temp_diff < 10:
        return -45 # Parked (East)
    
    # Expansion Logic
    expansion_factor = (effective_temp_diff - 10) / 40 # Max expansion at +50 delta
    expansion_factor = np.clip(expansion_factor, 0, 1)
    
    current_extension = expansion_factor * MAX_EXTENSION
    angle = -45 + (current_extension * DEG_PER_MM)
    return np.clip(angle, -45, 45)

def calculate_energy(solar_irradiance, angle_deviation):
    """
    Calculates power output. 
    If panel is pointing at sun (deviation 0), we get 100% power.
    """
    efficiency_loss = abs(angle_deviation) * 0.5 # Lose 0.5% power per degree error
    efficiency = max(0, 100 - efficiency_loss) / 100
    return (solar_irradiance / 1000) * PANEL_CAPACITY * efficiency

# --- 3. DATA SIMULATION MODULE (The Fake Sensors) ---
@st.cache_data
def generate_complete_data():
    # Time: 6:00 AM to 6:00 PM
    hours = np.linspace(6, 18, 100)
    
    data = []
    
    # Tracking Cumulative Energy
    total_energy = 0
    
    for i, h in enumerate(hours):
        # A. Base Weather Patterns
        # Sun peaks at noon (12)
        sun_curve = np.sin(((h-6)/12) * np.pi) 
        solar_irr = max(0, sun_curve * 1000)
        
        # Ambient temp rises with day
        ambient_temp = 25 + (sun_curve * 10) # 25C to 35C
        
        # Wax temp follows sun but gets much hotter
        wax_temp = ambient_temp + (sun_curve * 40) # Up to 75C
        
        # B. Inject "Rain Event" (2:00 PM to 3:00 PM)
        is_raining = 0
        if 14 <= h <= 15:
            is_raining = 1
            solar_irr = 200     # Dark clouds
            wax_temp = ambient_temp # Rapid cooling
        
        # C. Calculate Ideal Physics
        expected_angle = calculate_expected_angle(wax_temp, ambient_temp)
        
        # D. Inject "Mechanical Jam" (4:00 PM onwards)
        real_angle = expected_angle
        if h > 16:
            real_angle = 10 # Stuck at 10 degrees while expected goes back to -45
            
        # E. Calculate Energy
        deviation = abs(real_angle - expected_angle)
        power_output = calculate_energy(solar_irr, deviation)
        total_energy += power_output * (12/100) # Integration over time step
        
        data.append({
            'Time': f"{int(h):02d}:{int((h%1)*60):02d}",
            'Ambient_Temp': ambient_temp,
            'Wax_Temp': wax_temp,
            'Solar_Irradiance': int(solar_irr),
            'Real_Angle': real_angle,
            'Expected_Angle': expected_angle,
            'Power_Output': round(power_output, 1),
            'Total_Energy': round(total_energy, 1),
            'Is_Raining': is_raining
        })
        
    return pd.DataFrame(data)

df = generate_complete_data()

# --- 4. UI DASHBOARD MODULE (The Website) ---
# Initialize
if 'idx' not in st.session_state:
    st.session_state.idx = 0

# Sidebar
st.sidebar.title("🛠 Debug Panel")
speed = st.sidebar.slider("Simulation Speed", 0.1, 1.0, 0.3)
if st.sidebar.button("Restart"):
    st.session_state.idx = 0

# Main Header
st.title("☀️ Eco-Track: AI-Monitored Wax Solar System")
st.markdown("Live Telemetry | Pattern Recognition | Predictive Maintenance")

# Loop
if st.session_state.idx < len(df):
    row = df.iloc[st.session_state.idx]
    
    # --- LOGIC: FAULT DETECTION ---
    deviation = abs(row['Real_Angle'] - row['Expected_Angle'])
    status = "OPTIMAL"
    status_color = "success" # Green
    
    if row['Is_Raining']:
        status = "RAIN MODE (RETRACTING)"
        status_color = "info" # Blue
    elif deviation > 10 and row['Solar_Irradiance'] > 500:
        status = "⚠️ CRITICAL: MECHANICAL JAM"
        status_color = "error" # Red
        
    # --- VISUALS: KEY METRICS ---
    # Row 1: Energy & Environment
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Generate Power", f"{row['Power_Output']} W", f"Total: {row['Total_Energy']} Wh")
    c2.metric("Solar Irradiance", f"{row['Solar_Irradiance']} W/m²")
    c3.metric("Ambient Temp", f"{row['Ambient_Temp']:.1f} °C")
    c4.metric("Wax Temp", f"{row['Wax_Temp']:.1f} °C", delta=f"{row['Wax_Temp'] - row['Ambient_Temp']:.1f} °C Delta")
    
    # Row 2: Mechanical Health
    st.divider()
    c5, c6 = st.columns([3, 1])
    
    with c6:
        st.write("### System Status")
        if status_color == "success":
            st.success(status)
        elif status_color == "info":
            st.info(status)
        else:
            st.error(status)
            
        st.metric("Angle Deviation", f"{deviation:.1f}°", help="Difference between AI Prediction and Reality")
        
    with c5:
        st.write("### Digital Twin Tracking")
        # Live Chart
        chart_data = df.iloc[:st.session_state.idx+1]
        st.line_chart(chart_data[['Real_Angle', 'Expected_Angle']], color=["#0000FF", "#FF0000"])
        st.caption("Blue: Real Sensor Data | Red: AI Physics Model")

    # Increment
    time.sleep(speed)
    st.session_state.idx += 1
    st.rerun()

else:
    st.write("Daily Cycle Complete.")
    if st.button("Reset Day"):
        st.session_state.idx = 0
