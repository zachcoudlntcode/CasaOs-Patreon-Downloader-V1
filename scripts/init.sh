#!/bin/bash
set -e

# Default to PUID=1000 and PGID=1000 if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Initializing container with PUID: $PUID, PGID: $PGID"

# Update yt-dlp to ensure compatibility with latest features
echo "Updating yt-dlp to latest version..."
pip install -U yt-dlp

# Create the user if it doesn't exist with specified PUID/PGID
groupadd -g $PGID appuser || echo "Group with ID $PGID already exists"
useradd -u $PUID -g $PGID -d /config -s /bin/bash -M appuser || echo "User with ID $PUID already exists"

# Update ownership of application directories
chown -R $PUID:$PGID /downloads /config /scripts
chmod -R 755 /scripts

# Setup crontab for the appuser
crontab -u appuser /tmp/crontab

# Run the download script once at startup as appuser
su - appuser -c "/scripts/download_patreon.sh"

# Start cron in foreground
cron -f
