import csv
import os
from google.adk.plugins import BasePlugin
import json

# ─── TOKEN COUNTER PLUGIN ─────────────────────────────────────────────────────
# Fires on EVERY LLM call across all agents and sub-agents at any nesting depth

class TokenCounterPlugin(BasePlugin):

    def __init__(self):
        super().__init__(name="token_counter")
        self.input_tokens  = 0
        self.output_tokens = 0

    def reset(self):
        self.input_tokens  = 0
        self.output_tokens = 0

    async def after_model_callback(
        self, *, callback_context, llm_response
    ) -> None:
        meta = getattr(llm_response, "usage_metadata", None)
        if meta:
            self.input_tokens  += getattr(meta, "prompt_token_count",     0) or 0
            self.output_tokens += getattr(meta, "candidates_token_count", 0) or 0
        return None

# ─── SHARED PLUGIN INSTANCES ──────────────────────────────────────────────────
# One token_counter shared across all runners so all LLM calls are captured

token_counter = TokenCounterPlugin()


# ─── CSV LOGGING SETUP ────────────────────────────────────────────────────────

CSV_LOG_FILE = "logs/agent_runs2.csv"
CSV_HEADERS  = [
    "timestamp",
    "duration_seconds",
    "input_tokens",
    "output_tokens",
    "is_safe",
    "attempts",
    "main_agent_output"
]

def init_csv_log():
    """Create CSV with headers if it doesn't exist yet."""
    if not os.path.exists(CSV_LOG_FILE):
        with open(CSV_LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()

def append_csv_log(timestamp, duration_seconds, input_tokens, output_tokens, is_safe, attempts, main_agent_output):
    """Append one run's metrics to the CSV log."""
    with open(CSV_LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow({
            "timestamp":         timestamp,
            "duration_seconds":  round(duration_seconds, 3),
            "input_tokens":      input_tokens,
            "output_tokens":     output_tokens,
            "is_safe":           is_safe,
            "attempts":          attempts,
            "main_agent_output": json.dumps(main_agent_output) 
                                 if isinstance(main_agent_output, dict) 
                                 else str(main_agent_output)
        })
