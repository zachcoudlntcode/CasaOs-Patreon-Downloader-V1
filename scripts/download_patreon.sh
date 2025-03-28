#!/bin/bash
set -e

# Set PATH to ensure commands can be found
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

echo "=== Starting Patreon download at $(date) ==="

# Load config
CONFIG_FILE="/config/config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Check if we have credentials
COOKIES_FILE="/config/cookies.txt"
if [ ! -f "$COOKIES_FILE" ]; then
    echo "Error: Cookies file not found at $COOKIES_FILE"
    exit 1
fi

# Create log directory if it doesn't exist
LOG_DIR="/downloads/logs"
mkdir -p "$LOG_DIR"

# Create timestamped log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/patreon_download_$TIMESTAMP.log"
DETAILED_LOG="/downloads/detailed_download.log"

# Start logging
echo "Download started at $(date)" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "Detailed log: $DETAILED_LOG" | tee -a "$LOG_FILE"
echo "Running as user: $(whoami)" | tee -a "$LOG_FILE"
echo "Current directory: $(pwd)" | tee -a "$LOG_FILE"

# Process each creator from config - redirect to both console and log file
python /scripts/process_creators.py 2>&1 | tee -a "$LOG_FILE"

# Summarize download results
echo "=== Download Summary ===" | tee -a "$LOG_FILE"
echo "Download completed at: $(date)" | tee -a "$LOG_FILE"

# Print disk usage for downloads directory
echo -e "\nDownload directory usage:" | tee -a "$LOG_FILE"
du -sh /downloads/* | tee -a "$LOG_FILE"

echo "=== Completed Patreon download at $(date) ==="
echo "Next scheduled check will be in 3 hours" | tee -a "$LOG_FILE"

# Rotate logs if there are more than 20
find "$LOG_DIR" -type f -name "patreon_download_*.log" | sort | head -n -20 | xargs -r rm
