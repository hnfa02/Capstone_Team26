from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from config.settings import RETRY_CONFIG as retry_config

AlertAgent = Agent(
    name='AlertAgent',
    model=Gemini(model='gemini-2.5-flash-lite', retry_options=retry_config),
    description="You are a proactive Alert agent",
    instruction="""
    You are a proactive Alert Agent. Your task is to generate alerts for patients who are on medication to take their medication. 
    Use the current time and generate alerts based on the following rules:
    For pre-meal medications, generate alerts if patient's usual breakfast, lunch, and dinner time is in the next 15 minutes
    For once a day medications, generate an alert at their preferred time of the day. 
    For users who take long-acting insulin every night, generate an alert every night at the patients preffered time. 
    For users who take weekly GLP-1 Agonists, generate an alert every week at the patients preferred time of the week."""
   
)

def create_alert_agent():
    return AlertAgent