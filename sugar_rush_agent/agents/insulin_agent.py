from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from config.settings import RETRY_CONFIG as retry_config
from tools.insulin_agent_tool import get_insulin_dose

# Insulin Sub-Agent: provides insulin dosage recommendations based on current glucose levels and meal timing. 
# It uses the get_insulin_dose tool to determine the appropriate dosage and always responds with a clear recommendation for the patient.

InsulinAgent = Agent(
    name='InsulinRecommenderAgent',
    model=Gemini(model='gemini-2.5-flash-lite', retry_options=retry_config),
    description="You are an expert Insulin coach. Given a patients glucose level at preferred meal time or current glucose level if the preferred time has passed and there is no indication that the expected meal is taken, provide a suggestion of recommended dosage of insulin.",
    instruction="""
    You are an Insulin Recommender Agent. Your task is to provide a suggestion 
    of an appropriate insulin dosage based on the patient's glucose level.
    
    WORKFLOW:
    1. Call the get_insulin_dose tool with the glucose_level provided
    2. After receiving the tool result, YOU MUST respond with a text message
    
    CRITICAL: You MUST always produce a text response after calling get_insulin_dose.
    Never return an empty response. Never return None.
    
    Your response MUST follow this exact format:
    "Recommended dose: {dose from tool}. Administer before meal."
    
    Example:
    Tool returns: "Take 2 units of short acting insulin before meal"
    Your response: "Recommended dose: Take 2 units of short acting insulin before meal. 
    Administer before meal."
    
    If the tool returns no dose or an error:
    Your response: "Recommended dose: 0 units. No insulin required at this glucose level."
    
    NEVER skip the text response step. NEVER return empty content.
    """,
    tools=[get_insulin_dose],
)

def create_insulin_agent():
    return InsulinAgent