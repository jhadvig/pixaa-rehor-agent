#!/bin/bash
set -e

echo "pixaa-rehor-agent" > /home/botuser/app/.instance-id

# Instance-specific packages and tools go here:
# dnf install -y --nodocs <package>
# pip3.12 install <package>
# npm install -g <package>

# Override cycle timeout: 45 minutes (default is 30)
python3 -c "
import json
with open('/home/botuser/app/config.json') as f:
    cfg = json.load(f)
cfg['claude']['cycleTimeoutSeconds'] = 2700
with open('/home/botuser/app/config.json', 'w') as f:
    json.dump(cfg, f, indent=2)
"

echo "Instance setup complete: pixaa-rehor-agent"
