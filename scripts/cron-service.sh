#!/bin/bash
set -e

# This script runs as a helper to ensure cron jobs work properly

# Log start time
echo "=== Cron service helper started at $(date) ===" >> /downloads/cron-service.log

# Run the Patreon download script
/scripts/download_patreon.sh

# Log completion
echo "=== Cron service helper completed at $(date) ===" >> /downloads/cron-service.log