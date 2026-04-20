import re
import json

def extract_text_from_debug(debug_result):
    try:
        if isinstance(debug_result, list):
            for event in reversed(debug_result):
                if hasattr(event, "content") and event.content:
                    return event.content.parts[0].text
        return str(debug_result)
    except Exception:
        return str(debug_result)

def extract_clean_summary(main_json):
    summary = main_json.get("Output_Summary", "")
    if not summary:
        return {}
    if isinstance(summary, dict):
        return summary
    summary = re.sub(r"```json|```", "", summary).strip()
    if summary.startswith("{"):
        try:
            inner = json.loads(summary)
            return inner.get("Output_Summary", inner)
        except Exception:
            pass
    return summary