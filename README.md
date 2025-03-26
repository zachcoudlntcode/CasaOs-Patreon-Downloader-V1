# Patreon Downloader - Automated Docker Container

This Docker container automatically downloads content from Patreon creators without requiring any user interaction after initial setup.

## Setup Instructions

### 1. Prepare Configuration

The container requires two critical files in the `config` directory:

#### a. Create a cookies.txt file

You need to extract cookies from your browser after logging into Patreon:

1. Install a browser extension like "cookies.txt" for Chrome or "Export Cookies" for Firefox
2. Log in to Patreon with your account
3. Use the extension to export your cookies for the patreon.com domain
4. Save the exported file as `cookies.txt` in the `config` directory

#### b. Create a config.json file

Copy the example config and modify it:

```bash
cp config/config.json.example config/config.json
```

Edit `config.json` to include the creators you want to download from:

```json
{
  "creators": [
    {
      "name": "creatorusername",
      "days_back": 30
    }
  ]
}
```

- `name`: The username of the creator as it appears in their Patreon URL
- `days_back`: How many days of content to look back (optional, default: 30)
- `ytdlp_args`: Additional yt-dlp arguments (optional)

### 2. Build and Run the Container

```bash
# Create necessary directories
mkdir -p downloads config

# Place your cookies.txt and config.json in the config directory

# Build and start the container
docker-compose up -d
```

### 3. How It Works

- The container will immediately check for new content when started
- A scheduled cron job will check for new content every 6 hours
- Downloaded content is saved to the `downloads` directory, organized by creator name
- Already downloaded files are tracked in an archive to avoid duplicates
- Video files are automatically cleaned up:
  - Filenames are simplified (IDs are removed)
  - Metadata is added from descriptions
  - Extra files (thumbnails, descriptions, etc.) are removed

### 4. Logs

The container now provides detailed logging information:

```bash
# View container logs
docker-compose logs -f

# View main download logs
ls -la downloads/logs/
cat downloads/logs/patreon_download_YYYYMMDD_HHMMSS.log

# View detailed download progress log
cat downloads/detailed_download.log

# View cron execution log
cat downloads/cron.log
```

The logs show:
- Download progress with percentage complete
- Download speed
- Estimated time remaining
- File sizes
- Summary information when downloads complete

## CasaOS Installation

This application is designed to work smoothly with CasaOS. To install in CasaOS:

1. In CasaOS dashboard, go to "App Store"
2. Click "Custom App"
3. Use either method:
   
   **Method 1: Docker Compose**
   - Paste the contents of the `docker-compose.yml` file
   - Click "Install"
   
   **Method 2: Docker Run**
   - Use the following Docker run command:
   ```
   docker run -d \
     --name patreon-downloader \
     -v /DATA/AppData/patreon-downloader/downloads:/downloads \
     -v /DATA/AppData/patreon-downloader/config:/config \
     -e TZ=America/New_York \
     -e PUID=1000 \
     -e PGID=1000 \
     -e PYTHONUNBUFFERED=1 \
     --restart unless-stopped \
     patreon-downloader:latest
   ```

4. After installation, create the required configuration files in `/DATA/AppData/patreon-downloader/config/`:
   - `cookies.txt` - Your Patreon cookies
   - `config.json` - Your creator configuration

### File Structure in CasaOS

When installed in CasaOS, your files will be organized as follows:

```
/DATA/AppData/patreon-downloader/
├── config/
│   ├── cookies.txt      # Your Patreon cookies
│   ├── config.json      # Creator configuration
│   └── archive.txt      # Download history (created automatically)
└── downloads/
    ├── logs/            # Download logs
    └── [creator-name]/  # Downloaded content, organized by creator
```

## Advanced Options

### Customizing the Schedule

Edit the `crontab` file to change how often content is checked. The default is every 6 hours.

### Forcing a Manual Download

If you want to force a download immediately:

```bash
docker-compose exec patreon-downloader /scripts/download_patreon.sh
```

### Updating yt-dlp

The container periodically checks for yt-dlp updates, but you can manually update:

```bash
docker-compose exec patreon-downloader pip install -U yt-dlp
```

## Troubleshooting

### Authentication Issues

If downloads fail with authentication errors:
- Ensure your cookies.txt file is up to date
- Check that you're properly logged into Patreon when you export cookies
- Some content might require a specific patron tier access

### Download Failures

If specific downloads fail:
- Check the logs for error messages
- Try increasing verbosity by adding `"ytdlp_args": "--verbose"` to the creator's config
- Some Patreon content may use non-standard delivery methods that yt-dlp cannot handle

## References

For more information about yt-dlp options, refer to the [official documentation](https://github.com/yt-dlp/yt-dlp#readme).
