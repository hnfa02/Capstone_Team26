# Capstone Team 26: Team Anti-Sugar Rush

## Project Introduction

For our MADS Capstone Project, we've developed an AI system that provides personalized, actionable recommendations based on a user’s glucose levels. Additionally, we developed a glucose prediction model for the Agent framework to use. Our tool will take in user input including information such as current glucose, meal preferences, last meal timing and carbs, any medications, and more. The system then can provide recommendations for meals, exercise, and insulin to keep users glucose in the recommended healthy range. The system can also provide alerts for any medications.

## Project Features

- Glucose Prediction Model
- AI Agent Framework + Evaluation and Testing Pipeline
- Streamlit App for interacting with Agent

## Repo Structure Overview:
* Agents Code - Jupyter Notebook : folder with jupyter notebook to build and run agent along with required models and files
* Agest Code System Evaluation : code and input for agent eval metrics
* Agents Testing : code to build agent test cases along with necessary inputs
* Glucose Prediction Model : code for full glucose prediction model pipeline including data cleaning and model testing
* sugar_rush_agent_app: code for streamlit app
  
### Full Repo Structure:
```
.
├── Agents Code - Jupyter Notebook/
│   ├── MADS699-Capstone-Project - Team 26.ipynb   # jupyter notebook to build and run agent
│   ├── all_models.pkl                             # glucose prediction model used
│   ├── traincalc-met-values-latest.csv            # MET Data
│   └── user_history.csv                           # user glucose history data
├── Agents Code System Evaluation/
│   ├── Agents_Evaluation.ipynb                    # code to run eval metrics
│   └── test_results.csv                           # input for eval metrics
├── Agents Testing/
│   ├── Test_Cases - AI Agents.ipynb               # build agent test cases jupyter notebook
│   ├── capstone_agents_pipeline.py                # build agent test cases python file 
│   ├── model_2301.joblib                          # glucose prediction model used
│   └── val_df.csv                                 # sample user glucose data
├── glucose_prediction_model/        # prediction models, cleaning, training
│   ├── Glucose Data Cleaning and Prediction Modelling.ipynb
├── past_version_archive/            # older versions of agent framework
├── sugar_rush_agent_app/            # Streamlit app
│   ├── agents/                      # all agent implementations
│   ├── config/
│   │   └── settings.py              # API keys, retry settings
│   ├── core/
│   │   ├── controller.py            # main agent runner (safety + formatter)
│   │   ├── logging.py               # logging functions
│   │   └── utils.py                 # helper functions
│   ├── data/                        # MET data
│   ├── logs/                        # log files
│   ├── tools/                       # all agent tools
│   ├── models/
│   │   ├── all_models.pkl           # trained model
│   │   └── user_history.csv         # glucose user history data
│   ├── .env
│   └── app.py                       # Streamlit UI
├── README.md
├── data_access_statement.md
└── requirements.txt
```
## Usage

```
# clone repository
git clone https://github.com/[username]/Capstone_Team26.git
cd Capstone_Team26

# install required dependencies
pip install -r requirements.txt
```
### Required APIs

For this project, you will need API keys for USDA FoodCentral API as well as Gemini API key. Any other LLM APIs compatible with google-adk may also be an option, however, we have only tested our code with gemini-2.5-flash. Different models may result in different outcomes.
* Instructions for USDA FoodCentral API can be found in the data_access_statement.md file
* Gemini API key can be obtained through Google Cloud Platform or Google AI Studio

### Jupyter Notebooks

Glucose Prediction Model Prerequisite:
* We were unable to save glucose dataset in github as file size was too large, glucose dataset can be found in source linked in data_access_statement.md file

For AI Agent Framework + Eval and Testing Pipeline as well as Glucose Prediction Model, open desired jupyter notebook and run notebook

### Streamlit App Usage

First in sugar_rush_agent_app/.env add Food and Gemini API keys

```
cd sugar_rush_agent_app
streamlit run app.py
```

