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

    # Create runners
    SafetyRunner = InMemoryRunner(agent=SafetyAgent, plugins=[LoggingPlugin(), token_counter])
    FormatterRunner = InMemoryRunner(agent=FormatterAgent, plugins=[LoggingPlugin(), token_counter])

    token_counter.reset()

    # Timing
    run_start = datetime.utcnow()
    run_timestamp = run_start.isoformat()

    # Loop state
    attempt = 0
    violations = []
    clean_summary = None
    final_output = None
    final_is_safe = False

    while attempt < max_retries:
        print(f"\n===== ATTEMPT {attempt + 1} =====")

        # Create fresh Main runner each attempt
        MainRunner = InMemoryRunner(agent=Main_agent, plugins=[LoggingPlugin(), token_counter])

        # Payload
        payload = {
            "user_input": user_input,
            "previous_output": clean_summary if attempt > 0 else None,
            "violations": violations if attempt > 0 else []
        }

        # ---------------- RUN MAIN AGENT ----------------
        raw_main = await MainRunner.run_debug(json.dumps(payload))
        main_text = extract_text_from_debug(raw_main)

        try:
            main_json = json.loads(main_text)
        except:
            main_json = {"Output_Summary": main_text}

        clean_summary = extract_clean_summary(main_json)
        final_output = clean_summary

        print("\n--- MAIN OUTPUT ---")
        print(json.dumps(clean_summary, indent=2))

        # ---------------- RUN SAFETY AGENT ----------------
        safety_payload = json.dumps({"Output_Summary": clean_summary})
        raw_safety = await SafetyRunner.run_debug(safety_payload)
        safety_text = extract_text_from_debug(raw_safety)

        try:
            safety_text_clean = re.sub(r"```json|```", "", safety_text).strip()
            safety_json = json.loads(safety_text_clean)
        except:
            safety_json = {
                "safe": False,
                "violations": ["Safety parsing failed"]
            }

        print("\n--- SAFETY OUTPUT ---")
        print(json.dumps(safety_json, indent=2))

        safe = safety_json.get("safe", False)
        new_violations = safety_json.get("violations", [])

        # Detect stuck loop
        if not safe and new_violations == violations and attempt > 0:
            return {
                "status": "failed",
                "reason": "Repeated violations",
                "violations": new_violations,
                "last_output": clean_summary
            }

        violations = new_violations

        # ✅ SAFE → FORMAT + RETURN
        if safe:
            fmt_payload = json.dumps({"validated_output": clean_summary})
            raw_fmt = await FormatterRunner.run_debug(fmt_payload)
            readable = extract_text_from_debug(raw_fmt)

            final_is_safe = True
            result = readable
            break

        attempt += 1

    else:
        # Max retries hit
        result = {
            "status": "failed",
            "reason": "Max retries exceeded",
            "violations": violations,
            "last_output": clean_summary
        }

    # ---------------- LOGGING ----------------
    duration = (datetime.utcnow() - run_start).total_seconds()

    append_csv_log(
        timestamp=run_timestamp,
        duration_seconds=duration,
        input_tokens=token_counter.input_tokens,
        output_tokens=token_counter.output_tokens,
        is_safe=final_is_safe,
        attempts=attempt + 1,
        main_agent_output=final_output
    )

    return result