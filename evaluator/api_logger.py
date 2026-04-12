import os
import threading
from datetime import datetime, timezone

import config

_lock = threading.Lock()
_dir_created = False


def log_api_call(messages, response_text, duration_ms, error=None):
    """Append a markdown block for an LLM API call. No-op when disabled."""
    if not config.LLM_API_LOG_ENABLED:
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = []
    lines.append(f"## {ts} — {duration_ms}ms")
    if error:
        lines.append(f"**Error:** {error}")
    lines.append("")
    lines.append("### Prompt")
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        lines.append(f"**{role}:**")
        lines.append(content)
        lines.append("")
    lines.append("### Response")
    lines.append(response_text or "(empty)")
    lines.append("")
    lines.append("---")
    lines.append("")

    try:
        global _dir_created
        with _lock:
            if not _dir_created:
                os.makedirs(os.path.dirname(config.LLM_API_LOG_FILE), exist_ok=True)
                _dir_created = True
            with open(config.LLM_API_LOG_FILE, "a", encoding="utf-8") as f:
                f.write("\n".join(lines))
    except Exception:
        pass
