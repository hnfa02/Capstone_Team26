# Gen AI Disclaimer: ChatGPT used
import streamlit as st
import asyncio
from core.controller import run_main_with_safety
from agents import initialize_agents

agents = initialize_agents()


agents = {"main": agents['main'], "safety": agents['safety'], "formatter": agents['formatter']}

st.set_page_config(page_title="Diabetes AI Coach", layout="wide")

st.title("🩺 Diabetes AI Coach")

# ---------------- INPUT FORM ----------------
with st.form("user_input_form"):
    col1, col2 = st.columns(2)

    with col1:
        min_past = st.number_input("Min Past Glucose", value=90)
        max_past = st.number_input("Max Past Glucose", value=200)
        current_glucose = st.number_input("Current Glucose", value=165)

        last_meal = st.text_input("Last Meal", "Breakfast at 7:00 AM ET")
        last_meal_carbs = st.text_input("Last Meal Carbs", "40 g")
        
        current_time = st.text_input("Current Time", "1:30 PM ET")

    with col2:
        weight = st.text_input("Weight", "75 kg")
        height = st.text_input("Height", "1.65 m")
        diet = st.selectbox("Diet", ["Non-Veg", "Veg", "Vegan"])

        breakfast = st.text_input("Breakfast Time", "7:00 AM ET")
        lunch = st.text_input("Lunch Time", "12:30 PM ET")
        dinner = st.text_input("Dinner Time", "7:00 PM ET")

        oral_med = st.selectbox("Oral Medication", ["pre-meal", "none"])
        insulin = st.selectbox("Insulin", ["yes", "no"])
        long_insulin = st.text_input("Long Acting Insulin", "Yes, every night 9PM ET")
        glp1 = st.selectbox("GLP-1", ["yes", "no"])

    submit = st.form_submit_button("Run AI Coach")

# ---------------- RUN ----------------
if submit:
    user_input = f"""
    min_past = {min_past}
    max_past = {max_past}
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

    with st.spinner("Running AI agents..."):
        result = asyncio.run(run_main_with_safety(user_input, agents))

    st.success("Done!")

    st.text_area("AI Recommendation", result, height=500)