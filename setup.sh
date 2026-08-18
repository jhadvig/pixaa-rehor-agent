#!/bin/bash
set -e

echo "pixaa-rehor-agent" > /home/botuser/app/.instance-id

# Override cycle timeout: 45 minutes (default is 30).
# The console repo's yarn install can take 15+ minutes, causing
# the default 30-minute session to timeout before the agent
# finishes implementing and testing its fix.
python3 -c "
import json
with open('/home/botuser/app/config.json') as f:
    cfg = json.load(f)
cfg['claude']['cycleTimeoutSeconds'] = 2700
with open('/home/botuser/app/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"

echo "Instance setup complete: pixaa-rehor-agent"
