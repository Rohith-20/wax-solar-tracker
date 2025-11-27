import streamlit as st
import pandas as pd
import numpy as np
import time
import math

# --- 1. CONFIGURATION & PHYSICAL CONSTANTS ---
st.set_page_config(page_title="Solar-X Wax Tracker", page_icon="☀️", layout="wide")

# Mechanical Limits
MAX_ROTATION = 60        # Panel can move -60 (East) to +60 (West) -> Total 120 degrees
PANEL_CAPACITY = 250     # Watts (Standard single panel size)
MELTING_POINT = 25       # Wax starts expanding
FULL_EXPANSION_TEMP = 75 # Wax is fully expanded

# --- 2. PHYSICS ENGINE (The Brain) ---

def get_sun_position(hour):
    """
    Returns the Sun's angle in the sky based on time.
    6:00 AM = -90 degrees (Horizon East)
    12:00 PM = 0 degrees (Zenith)
    6:00 PM = +90 degrees (Horizon West)
    """
    # Map 6-18 hours to -90 to +90 degrees
    return (hour - 12) * 15

def get_wax_expansion_angle(wax_temp, ambient_temp):
    """
    Calculates Panel Angle based on Wax Temperature.
    Restricted to MAX_ROTATION (±60 degrees).
    """
    effective_temp = wax_temp - ambient_temp
    
    # Deadband: Wax needs to be at least 10C hotter than air to work
    if effective_temp < 10:
        return -MAX_ROTATION # Parked at East
        
    # Expansion Logic (Linear for simulation)
    # Map temp range (10 to 50 delta) to angle range (-60 to +60)
    progress = (effective_temp - 10) / 40 
    progress = np.clip(progress, 0, 1)
    
    # Convert 0-1 progress to -60 to +60 degrees
    angle = -MAX_ROTATION + (progress * (MAX_ROTATION * 2))
    return int(angle)

def calculate_power_output(irradiance, sun_angle, panel_angle):
    """
    Calculates power based on Cosine Loss.
    If Panel is at 60 deg but Sun is at 80 deg, we lose power.
    """
    # Calculate angular error
    error_deg = abs(sun_angle - panel_angle)
    
    # Cosine efficiency (convert deg to radians)
    efficiency = math.cos(math.radians(error_deg))
    efficiency = max(0, efficiency) # Cannot be negative
    
    return int(irradiance * (PANEL_CAPACITY / 1000) * efficiency)

def get_working_condition(irradiance):
    """Returns the Status Label based on Irradiance Energy"""
    if irradiance < 200:
        return "LOW", "gray"
    elif irradiance < 600:
        return "MEDIUM", "orange"
    else:
        return "HIGH", "green"

# --- 3. DATA SIMULATION (The "Predefined" 7 AM - 6 PM Data) ---
@st.cache_data
def generate_day_data():
    # Create time range: 7:00 AM to 6:00 PM
    hours = np.linspace(7, 18, 100)
    data = []
    
    for h in hours:
        # 1. Simulate Environment
        sun_angle = get_sun_position(h)
        
        # Sun curve (Sine wave peak at noon)
        sun_intensity = np.sin(((h-6)/12) * np.pi)
        irradiance = int(max(0, sun_intensity * 1000))
        
        # Temps
        ambient_temp = 25 + (sun_intensity * 10) # 25C - 35C
        
        # Wax gets hot! (Greenhouse effect simulation)
        # Normal operation: Wax follows sun intensity
        wax_temp = ambient_temp + (sun_intensity * 50) 
        
        # 2. Simulate Mechanics
        panel_angle = get_wax_expansion_angle(wax_temp, ambient_temp)
        
        # 3. Simulate Power
        power = calculate_power_output(irradiance, sun_angle, panel_angle)
        
        # 4. Status
        condition, color = get_working_condition(irradiance)
        
        data.append({
            "Time": f"{int(h):02d}:{int((h%1)*60):02d}",
            "Sun_Angle": int(sun_angle),
            "Panel_Angle": panel_angle,
            "Ambient_Temp": round(ambient_temp, 1),
            "Wax_Temp": round(wax_temp, 1),
            "Irradiance": irradiance,
            "Power": power,
            "Condition": condition,
            "Color": color
        })
        
    return pd.DataFrame(data)

df = generate_day_data()

# --- 4. DASHBOARD UI ---

# Initialize Session State for Animation
if 'idx' not in st.session_state:
    st.session_state.idx = 0

# Sidebar Control
with st.sidebar:
    st.header("⚙️ Simulation Control")
    speed = st.slider("Animation Speed", 0.05, 1.0, 0.2)
    if st.button("Restart Day"):
        st.session_state.idx = 0
    
    st.divider()
    st.markdown("""
    **System Limits:**
    - Max Rotation: ±60°
    - Panel Size: 250W
    - Wax Melting: 25°C
    """)

# Main Layout
st.title("☀️ Solar-X: Wax-Actuated Tracking System")
st.markdown("**Real-time Telemetry & Power Generation Monitor**")

if st.session_state.idx < len(df):
    row = df.iloc[st.session_state.idx]
    
    # --- SECTION 1: LIVE CAM & STATUS ---
    col_cam, col_status = st.columns([1, 2])
    
    with col_cam:
        st.write("📷 **Live Site View**")
        # Placeholder image of a solar panel
        st.image("https://images.unsplash.com/photo-1509391366360-2e959784a276?q=80&w=1000&auto=format&fit=crop", 
                 caption=f"Panel Position: {row['Panel_Angle']}°", use_column_width=True)
    
    with col_status:
        # Working Condition Badge
        st.write("### System Efficiency Status")
        if row['Color'] == "green":
            st.success(f"🟢 **{row['Condition']} OUTPUT** - Tracking Optimal")
        elif row['Color'] == "orange":
            st.warning(f"🟠 **{row['Condition']} OUTPUT** - Partial Sun")
        else:
            st.info(f"⚪ **{row['Condition']} OUTPUT** - Low Light / Morning")
            
        st.divider()
        
        # Key Metrics Grid
        m1, m2, m3 = st.columns(3)
        m1.metric("⚡ Generated Power", f"{row['Power']} W")
        m2.metric("☀ Solar Irradiance", f"{row['Irradiance']} W/m²")
        m3.metric("📐 Panel Angle", f"{row['Panel_Angle']}°", delta=f"Sun at {row['Sun_Angle']}°")
        
        m4, m5, m6 = st.columns(3)
        m4.metric("🌡 Wax Temp", f"{row['Wax_Temp']}°C")
        m5.metric("🌡 Ambient Temp", f"{row['Ambient_Temp']}°C")
        m6.metric("⏳ Time", row['Time'])

    # --- SECTION 2: CHARTS ---
    st.subheader("📊 Performance Analytics")
    
    # 1. Tracking Accuracy Chart
    chart_data = df.iloc[:st.session_state.idx+1]
    
    # Prepare data for line chart
    angle_chart = pd.DataFrame({
        'Sun Position': chart_data['Sun_Angle'],
        'Panel Position': chart_data['Panel_Angle']
    })
    st.line_chart(angle_chart, color=["#FFD700", "#0000FF"]) 
    st.caption("Yellow: Sun Angle (-90 to +90) | Blue: Panel Angle (Limited to ±60)")

    # Auto-increment logic
    time.sleep(speed)
    st.session_state.idx += 1
    st.rerun()

else:
    st.success("✅ Daily Generation Cycle Complete.")
    if st.button("Start New Day"):
        st.session_state.idx = 0
