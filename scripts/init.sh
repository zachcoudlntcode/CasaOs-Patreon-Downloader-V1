#!/bin/bash
set -e

# Default to PUID=1000 and PGID=1000 if not provided
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Initializing container with PUID: $PUID, PGID: $PGID"

# Update yt-dlp to ensure compatibility with latest features
echo "Updating yt-dlp to latest version..."
pip install -U yt-dlp

# Run compatibility check
echo "Checking yt-dlp compatibility..."
python /scripts/check_ytdlp.py

# Create the user if it doesn't exist with specified PUID/PGID
groupadd -g $PGID appuser || echo "Group with ID $PGID already exists"
useradd -u $PUID -g $PGID -d /config -s /bin/bash -M appuser || echo "User with ID $PUID already exists"

# Update ownership of application directories
chown -R $PUID:$PGID /downloads /config /scripts
chmod -R 755 /scripts

# Create cron log file and set proper permissions
touch /downloads/cron.log
chown $PUID:$PGID /downloads/cron.log

# Copy crontab to a temp file that cron can actually use
cp /tmp/crontab /tmp/appuser_crontab
chown $PUID:$PGID /tmp/appuser_crontab

# Setup crontab for the appuser
crontab -u appuser /tmp/appuser_crontab

# Add a test cron job to verify cron is working 
echo "* * * * * echo \"Cron test at \$(date)\" >> /downloads/cron_test.log 2>&1" >> /tmp/root_crontab
crontab /tmp/root_crontab

# Log cron configuration
echo "Cron configuration for appuser:"
crontab -u appuser -l
echo "Cron configuration for root:"
crontab -l

# Run the download script once at startup as appuser
su - appuser -c "/scripts/download_patreon.sh"

# Enable cron logging for debugging
echo "SHELL=/bin/bash" > /etc/crontab
echo "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" >> /etc/crontab
echo "MAILTO=\"\"" >> /etc/crontab
echo "CRON_LOG=yes" >> /etc/crontab

# Start cron in foreground with more verbose logging
cron -f
