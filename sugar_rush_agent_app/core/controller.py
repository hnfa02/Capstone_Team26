import json
import re
from datetime import datetime
from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin

from core.utils import extract_text_from_debug, extract_clean_summary
from core.logging import token_counter, append_csv_log


# --------------------------------------------------
# MAIN CONTROLLER FUNCTION
# --------------------------------------------------

async def run_main_with_safety(user_input, agents, max_retries=2):
    """
    Runs Main Agent → Safety Agent loop with retry logic.
    
    agents = {
        "main": Main_agent,
        "safety": SafetyAgent,
        "formatter": FormatterAgent
    }
    """

    Main_agent = agents["main"]
    SafetyAgent = agents["safety"]
    FormatterAgent = agents["formatter"]


    SafetyAgentrunner    = InMemoryRunner(agent=SafetyAgent,    plugins=[LoggingPlugin(), token_counter])
    FormatterAgentRunner = InMemoryRunner(agent=FormatterAgent, plugins=[LoggingPlugin(), token_counter])

    token_counter.reset()
    run_timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    run_start     = datetime.utcnow()

    attempt                  = 0
    violations               = []
    corrected_recommendation = None
    clean_summary            = None
    final_is_safe            = False
    final_output             = None
    result                   = None

    while attempt < max_retries:

        attempt += 1      
        
        print(f"\n========== ATTEMPT {attempt} ==========")

        MainAgentrunner = InMemoryRunner(agent=Main_agent, plugins=[LoggingPlugin(), token_counter])

        main_payload = {
            "user_input":      user_input,
            "previous_output": clean_summary if attempt > 1 else None,
            "violations":      violations    if attempt > 1 else []
        }

        raw_response = await MainAgentrunner.run_debug(json.dumps(main_payload))
        main_text    = extract_text_from_debug(raw_response)

        try:
            main_json = json.loads(main_text)
        except Exception:
            main_json = {"Output_Summary": main_text}

        print("\n--- MAIN OUTPUT ---")
        print(json.dumps(main_json, indent=2))

        clean_summary = extract_clean_summary(main_json)
        final_output  = clean_summary

        print("\n--- CLEAN SUMMARY SENT TO SAFETY ---")
        print(json.dumps(clean_summary, indent=2) if isinstance(clean_summary, dict) else clean_summary)

        safety_payload = json.dumps({"Output_Summary": clean_summary})
        raw_safety     = await SafetyAgentrunner.run_debug(safety_payload)
        safety_text    = extract_text_from_debug(raw_safety)

        print("\n--- RAW SAFETY TEXT ---")
        print(safety_text)

        try:
            safety_text_clean = re.sub(r"```json|```", "", safety_text).strip()
            safety_result     = json.loads(safety_text_clean)
        except Exception:
            safety_result = {
                "safe":       False,
                "violations": ["Could not parse safety agent response"],
            }

        print("\n--- SAFETY OUTPUT ---")
        print(json.dumps(safety_result, indent=2))

        safe           = safety_result.get("safe", False)
        new_violations = safety_result.get("violations", [])

        # ── Check if violations are repeating (agent is stuck) ────────────────
        if not safe and new_violations == violations and attempt > 1:
            final_is_safe = False
            result = {
                "status":      "failed",
                "reason":      "Repeated violations — agent is stuck",
                "attempts":    attempt,    # ← always correct now
                "violations":  new_violations,
                "last_output": clean_summary
            }
            break

        violations = new_violations

        # ── Safe: run formatter and return ────────────────────────────────────
        if safe:
            fmt_payload = json.dumps({"validated_output": clean_summary})
            raw_fmt     = await FormatterAgentRunner.run_debug(fmt_payload)
            readable    = extract_text_from_debug(raw_fmt)

            final_is_safe = True
            result = {
                "status":            "safe",
                "attempts":          attempt,    # ← always correct now
                "readable_output":   readable,
                "structured_output": clean_summary
            }
            break

    # ── Max retries exhausted ─────────────────────────────────────────────────
    if result is None:
        final_is_safe = False
        result = {
            "status":      "failed",
            "reason":      "Max retries exceeded",
            "attempts":    attempt,        # ← correct: equals MAX_RETRIES
            "violations":  violations,
            "last_output": clean_summary
        }

    duration = (datetime.utcnow() - run_start).total_seconds()
    append_csv_log(
        timestamp         = run_timestamp,
        duration_seconds  = duration,
        input_tokens      = token_counter.input_tokens,
        output_tokens     = token_counter.output_tokens,
        is_safe           = final_is_safe,
        attempts          = result["attempts"],    # ← read from result dict
        main_agent_output = final_output
    )

    return result