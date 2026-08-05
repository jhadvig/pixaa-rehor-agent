#!/bin/bash
set -e

echo "pixaa-rehor-agent" > /home/botuser/app/.instance-id

# Instance-specific packages and tools go here:
# dnf install -y --nodocs <package>
# pip3.12 install <package>
# npm install -g <package>

echo "Instance setup complete: pixaa-rehor-agent"
