#!/bin/bash
# Check evonic-improver progress and send WhatsApp update

IMPROVER_DIR=~/dev/evonic-llm-eval/improver
TARGET="+14793181117"

# Count files
FILES=$(ls -1 $IMPROVER_DIR/*.py 2>/dev/null | xargs -I{} basename {} | tr '\n' ', ' | sed 's/,$//')
FILES_COUNT=$(ls -1 $IMPROVER_DIR/*.py 2>/dev/null | wc -l)

# Check specific files
HAS_COMPARATOR=$([[ -f "$IMPROVER_DIR/comparator.py" ]] && echo "✅" || echo "❌")
HAS_PIPELINE=$([[ -f "$IMPROVER_DIR/pipeline.py" ]] && echo "✅" || echo "❌")
HAS_CLI=$([[ -f ~/dev/evonic-llm-eval/run_improve.py ]] && echo "✅" || echo "❌")

# Check if tmux session exists
if tmux has-session -t evonic-improver 2>/dev/null; then
    STATUS="🔄 Running"
    CPU=$(ps aux | grep "[c]laude" | awk '{print $3}')
    MSG="*evonic-improver*
Status: $STATUS (CPU: ${CPU:-0}%)
Files: $FILES_COUNT/6

$HAS_COMPARATOR comparator.py
$HAS_PIPELINE pipeline.py  
$HAS_CLI run_improve.py"
else
    # Session ended
    if [ "$FILES_COUNT" -ge 6 ]; then
        MSG="✅ *evonic-improver DONE!*
All $FILES_COUNT files created!"
    else
        MSG="⚠️ *evonic-improver stopped*
Files: $FILES_COUNT/6

$HAS_COMPARATOR comparator.py
$HAS_PIPELINE pipeline.py
$HAS_CLI run_improve.py

Need manual resume."
    fi
    
    # Remove cron after session ends
    crontab -l 2>/dev/null | grep -v "check-improver-progress" | crontab -
fi

# Send WhatsApp
openclaw message broadcast --channel whatsapp --targets "$TARGET" --message "$MSG" 2>/dev/null
