# Capstone Team 26: Team Anti-Sugar Rush

Repo Structure:
* past_version_archive/: contains past versions of agentic framework for references
* data/
  * data_access_statement.md: where to access all datasets + licensing info
  * traincalc-met-values-latest.csv: exercise MET csv file that is used by exercise agent
* tbd
  * final agent jupyter notebook
  * glucose prediction model jupyter notebook
* sugar_rush_agent: streamlit app
  * app.py: streamlit UI
  * config/
    * settings.py: API keys, retry settings
  * agents/: all agents
  * tools/: all tools for agents
  * models/: glucose prediction model
  * core/
    * controller.py: main function to run agent with safety agent + formatter agent
    * logging.py: logging functions
    * utils.py: helper functions
  * data/: MET data
  * logs/: log data

**Streamlit App Usage**
1. in .env file add api keys
2. run app.py then run streamlit command provided ex/ "streamlit run app.py"
