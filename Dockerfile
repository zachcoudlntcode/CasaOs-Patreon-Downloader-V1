FROM python:3.11-slim

# Install dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    aria2 \
    ca-certificates \
    cron \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp and requests
RUN pip install --no-cache-dir yt-dlp requests

# Setup directories
RUN mkdir -p /downloads /config /scripts

# Copy scripts
COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh /scripts/*.py

# Set up cron job
COPY crontab /tmp/crontab

# Add s6-overlay for proper init
COPY --chown=root:root scripts/init.sh /init.sh
RUN chmod +x /init.sh

# Volume definitions
VOLUME /downloads
VOLUME /config

# Set working directory
WORKDIR /downloads

ENTRYPOINT ["/init.sh"]
