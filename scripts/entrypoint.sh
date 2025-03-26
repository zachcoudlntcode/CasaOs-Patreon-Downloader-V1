#!/bin/bash
set -e

# Run the download script once at startup
su - ytdlp -c "/scripts/download_patreon.sh"

# Start cron in foreground
cron -f
