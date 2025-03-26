#!/usr/bin/env python3
import json
import os
import subprocess
import datetime
import time
import logging
import sys
import re

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/downloads/detailed_download.log')
    ]
)
logger = logging.getLogger('patreon_downloader')

def load_config():
    with open('/config/config.json', 'r') as f:
        return json.load(f)

def download_creator(creator, archive_file, cookies_file, download_dir):
    """Download content from a specific creator"""
    
    creator_url = f"https://www.patreon.com/{creator['name']}/posts"
    output_template = os.path.join(download_dir, creator['name'], '%(title)s [%(id)s].%(ext)s')
    
    days_back = creator.get('days_back', 30)
    date_after = (datetime.datetime.now() - datetime.timedelta(days=days_back)).strftime("%Y%m%d")
    
    logger.info(f"Processing creator: {creator['name']} (looking back {days_back} days)")
    
    cmd = [
        'yt-dlp',
        '--cookies', cookies_file,
        '--download-archive', archive_file,
        '--dateafter', date_after,
        '-o', output_template,
        '--write-info-json',
        '--write-description',
        '--write-thumbnail',
        '--restrict-filenames',
        '--progress',           # Show download progress
        '--newline',            # Each progress line on new line for better log readability
        '--progress-template', '[download] %(progress._percent_str)s of %(progress._total_bytes_str)s at %(progress._speed_str)s ETA %(progress._eta_str)s',
        creator_url
    ]
    
    # Add any custom yt-dlp arguments if specified
    if 'ytdlp_args' in creator:
        logger.info(f"Using custom arguments for {creator['name']}: {creator['ytdlp_args']}")
        cmd.extend(creator['ytdlp_args'].split())
    
    logger.info(f"Starting download for {creator['name']}")
    
    # Use Popen instead of run to capture output in real-time
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Variables to track progress and only log at 1% intervals
    last_logged_percent = -1
    progress_pattern = re.compile(r'\[download\].*?(\d+\.\d)%')
    
    # Log output in real-time
    for line in iter(process.stdout.readline, ''):
        line = line.strip()
        if not line:
            continue
            
        # Handle progress lines with percentage - only log at 1% intervals
        if line.startswith('[download]') and '%' in line:
            match = progress_pattern.match(line)
            if match:
                current_percent = float(match.group(1))
                # Only log if we've advanced at least 1% from last logged value
                if int(current_percent) > last_logged_percent:
                    logger.info(f"{creator['name']}: {line}")
                    last_logged_percent = int(current_percent)
            else:
                # Log non-percentage download messages (like completion)
                logger.info(f"{creator['name']}: {line}")
        elif '[info]' in line:
            logger.info(f"{creator['name']}: {line}")
        elif 'has already been downloaded' in line:
            logger.info(f"{creator['name']}: {line}")
        elif 'Downloading page' in line:
            logger.debug(f"{creator['name']}: {line}")
        else:
            logger.debug(f"{creator['name']}: {line}")
    
    process.stdout.close()
    return_code = process.wait()
    
    if return_code != 0:
        logger.error(f"Error downloading from {creator['name']} (return code: {return_code})")
    else:
        logger.info(f"Successfully completed processing {creator['name']}")

def main():
    try:
        logger.info("=== Starting Patreon content download process ===")
        
        config = load_config()
        archive_file = '/config/archive.txt'
        cookies_file = '/config/cookies.txt'
        download_dir = '/downloads'
        
        # Create archive file if it doesn't exist
        if not os.path.exists(archive_file):
            with open(archive_file, 'w') as f:
                pass
            logger.info(f"Created new archive file at {archive_file}")
        
        logger.info(f"Found {len(config['creators'])} creators to process")
        
        for creator in config['creators']:
            try:
                # Create creator directory if it doesn't exist
                creator_dir = os.path.join(download_dir, creator['name'])
                os.makedirs(creator_dir, exist_ok=True)
                
                logger.info(f"Starting download process for creator: {creator['name']}")
                download_creator(creator, archive_file, cookies_file, download_dir)
                
                # Add a small delay between creators to avoid rate limiting
                delay = 10
                logger.info(f"Waiting {delay} seconds before processing next creator...")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing creator {creator['name']}: {str(e)}", exc_info=True)
        
        logger.info("=== Patreon download process completed ===")
    
    except Exception as e:
        logger.critical(f"Fatal error in main process: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
