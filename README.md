# Capstone Team 26: Team Anti-Sugar Rush

Repo Structure:
* data/
  * data_access_statement.md: where to access all datasets + licensing info
  * traincalc-met-values-latest.csv: exercise MET csv file that is used by exercise agent
* glucose_prediction_model/ : contains all prediction model files, data cleaning, model training, etc.
* past_version_archive/: contains past versions of agentic framework for references
* sugar_rush_agent_app: streamlit app
  * app.py: streamlit UI
  * config/
    * settings.py: API keys, retry settings
  * agents/: all agents
  * tools/: all tools for agents
  * models/: glucose prediction model
    * all_models.pkl : actual model file
    * user_history.csv : csv file that contains user glucose history needed by model for prediction
  * core/
    * controller.py: main function to run agent with safety agent + formatter agent
    * logging.py: logging functions
    * utils.py: helper functions
  * data/: MET data
  * logs/: log data

**Streamlit App Usage**
1. in .env file add api keys
2. run app.py then run streamlit command provided ex/ "streamlit run app.py"
