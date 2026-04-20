# Gen AI Disclaimer: ChatGPT used

import streamlit as st
import asyncio
from core.controller import run_main_with_safety
from agents import initialize_agents
from datetime import time

# ---------------- INIT ----------------
agents = initialize_agents()
agents = {
    "main": agents['main'],
    "safety": agents['safety'],
    "formatter": agents['formatter']
}

st.set_page_config(
    page_title="Diabetes AI Coach",
    layout="wide",
    page_icon="🩺"
)

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.header("👤 Your Profile")

    weight = st.text_input("Weight", "75 kg")
    height = st.text_input("Height", "1.65 m")
    diet = st.selectbox("Diet", ["Non-Veg", "Veg", "Vegan"])

    st.divider()
    st.subheader("💊 Medication")

    oral_med = st.selectbox("Oral Medication", ["pre-meal", "none"])
    insulin = st.selectbox("Insulin", ["yes", "no"])
    long_insulin = st.text_input("Long Acting Insulin", "Yes, every night 9PM")
    glp1 = st.text_input("GLP-1", "Yes, weekly on Saturdays")

# ---------------- TITLE ----------------
st.title("🩺 Anti Sugar Rush")
st.caption("Your personalized diabetes AI coach")

# ---------------- TABS ----------------
tab1, tab2  = st.tabs(["✏️ Input", "🧠 AI Coach"])

# ---------------- SESSION STATE ----------------
if "result" not in st.session_state:
    st.session_state.result = None

# ---------------- TAB 1: INPUT ----------------
with tab1:
    st.subheader("Enter Today's Data")

    col1, col2 = st.columns(2)

    with col1:
        current_glucose = st.number_input(
            "Current Glucose (mg/dL)", min_value=50, max_value=400, value=165
        )

        last_meal = st.text_input("Last Meal", "Breakfast")
        last_meal_carbs = st.slider("Last Meal Carbs (g)", 0, 150, 40)

    with col2:
        breakfast = st.time_input("Breakfast Time", value=time(8, 0))
        lunch = st.time_input("Lunch Time", value=time(13, 0))
        dinner = st.time_input("Dinner Time", value=time(19, 0))
        current_time = st.time_input("Current Time", value=time(12, 0))

    submit = st.button("🚀 Run AI Coach")

    if submit:
        user_input = f"""
        current_glucose = {current_glucose}
        last_meal = {last_meal}
        current_time = {current_time}

        weight = {weight}
        height = {height}
        diet = {diet}

        usual_meal_times:
          breakfast = {breakfast}
          lunch = {lunch}
          dinner = {dinner}

        oral_medication = {oral_med}
        insulin = {insulin}
        long_acting_insulin = {long_insulin}
        glp1 = {glp1}
        """

        with st.spinner("🧠 Your AI coach is analyzing your data..."):
            result = asyncio.run(run_main_with_safety(user_input, agents))
            st.session_state.result = result

        st.success("Analysis complete! Check the AI Coach tab 👉")

# ---------------- TAB 2: AI COACH ----------------
with tab2:
    st.subheader("🧠 Your AI Coach Recommendations")

    if st.session_state.result:
        output = st.session_state.result['readable_output']

        st.markdown("### 📌 Key Advice")
        st.code(output, language="text")

        st.markdown("### 🎯 Next Steps")
        st.info("Follow the above recommendations and recheck glucose in 1–2 hours.")

    else:
        st.info("Run the AI Coach from the Input tab to see recommendations.")