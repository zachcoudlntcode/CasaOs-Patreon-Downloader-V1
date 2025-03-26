#!/usr/bin/env python3
import json
import os
import subprocess
import datetime
import time
import logging
import sys
import re
import fcntl
import shutil
import glob

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

def make_non_blocking(fd):
    """Make a file descriptor non-blocking"""
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
    return fd

def clean_filename(filename):
    """
    Clean up filenames by removing unnecessary patterns like [id], 
    excessive spaces, and special characters
    """
    # Remove [id] pattern that yt-dlp adds
    cleaned = re.sub(r'\s*\[[a-zA-Z0-9_-]+\](?=\.[a-zA-Z0-9]+$)', '', filename)
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Trim spaces at beginning and end
    cleaned = cleaned.strip()
    
    return cleaned

def add_metadata_to_video(video_file, info_json_file, description_file):
    """Add metadata from the description and info JSON to the video file"""
    if not os.path.exists(video_file) or not os.path.exists(info_json_file):
        logger.warning(f"Missing files needed for metadata: {video_file} or {info_json_file}")
        return False
    
    # Load info JSON
    try:
        with open(info_json_file, 'r', encoding='utf-8') as f:
            info = json.load(f)
        
        # Extract metadata
        title = info.get('title', '')
        upload_date = info.get('upload_date', '')
        uploader = info.get('uploader', '')
        
        # Get description from description file if available
        description = ""
        if os.path.exists(description_file):
            with open(description_file, 'r', encoding='utf-8') as f:
                description = f.read()
        
        # Build FFmpeg metadata arguments
        metadata_args = [
            'ffmpeg',
            '-i', video_file,
            '-c', 'copy',
            '-metadata', f'title={title}',
            '-metadata', f'author={uploader}',
            '-metadata', f'date={upload_date}',
            '-metadata', f'description={description}',
            f'{video_file}.temp'
        ]
        
        # Run FFmpeg to add metadata
        logger.info(f"Adding metadata to {os.path.basename(video_file)}")
        subprocess.run(metadata_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Replace original file with the one containing metadata
        os.remove(video_file)
        os.rename(f'{video_file}.temp', video_file)
        
        return True
        
    except Exception as e:
        logger.error(f"Error adding metadata: {str(e)}")
        # Clean up temp file if it exists
        if os.path.exists(f'{video_file}.temp'):
            os.remove(f'{video_file}.temp')
        return False

def clean_up_files(download_dir, creator_name):
    """
    Clean up downloaded files:
    1. Rename video files to remove ID
    2. Add metadata from info files
    3. Remove unnecessary files (JSON, description, thumbnails)
    """
    creator_dir = os.path.join(download_dir, creator_name)
    logger.info(f"Cleaning up files in {creator_dir}")
    
    # Group files by base name (without extension)
    file_groups = {}
    
    for file_path in glob.glob(os.path.join(creator_dir, '*')):
        if os.path.isfile(file_path):
            # Extract base name without extension and potential [id] suffix
            base_name = os.path.basename(file_path)
            # Match pattern like "Name [id].ext"
            match = re.match(r'(.+?)(\s*\[[a-zA-Z0-9_-]+\])(\.[a-zA-Z0-9]+)$', base_name)
            
            if match:
                name_without_id = match.group(1)
                id_part = match.group(2)
                extension = match.group(3)
                
                # Group files by their name without id
                if name_without_id not in file_groups:
                    file_groups[name_without_id] = {'id': id_part, 'files': []}
                
                file_groups[name_without_id]['files'].append((file_path, extension))
    
    # Process each group of files
    for base_name, group in file_groups.items():
        video_file = None
        info_json_file = None
        description_file = None
        other_files = []
        
        # Identify different file types
        for file_path, ext in group['files']:
            if ext.lower() in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
                video_file = file_path
            elif ext.lower() == '.info.json':
                info_json_file = file_path
            elif ext.lower() == '.description':
                description_file = file_path
            else:
                other_files.append(file_path)
        
        # Only proceed if we have a video file
        if video_file:
            # Create clean filename
            clean_name = clean_filename(base_name)
            video_ext = os.path.splitext(video_file)[1]
            new_video_path = os.path.join(creator_dir, f"{clean_name}{video_ext}")
            
            # Add metadata if we have the necessary files
            if info_json_file:
                add_metadata_to_video(video_file, info_json_file, description_file)
            
            # Rename the video file if the clean name is different
            if video_file != new_video_path:
                logger.info(f"Renaming {os.path.basename(video_file)} to {os.path.basename(new_video_path)}")
                # If destination exists, remove it first
                if os.path.exists(new_video_path):
                    os.remove(new_video_path)
                os.rename(video_file, new_video_path)
            
            # Delete other files
            for file_to_delete in [info_json_file, description_file] + other_files:
                if file_to_delete and os.path.exists(file_to_delete):
                    logger.debug(f"Deleting extra file: {os.path.basename(file_to_delete)}")
                    os.remove(file_to_delete)

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
        '--progress',               # Show download progress
        '--newline',                # Each progress line on new line for better log readability
        '--no-progress-template',   # Don't use custom progress template to avoid issues
        '--force-progress',         # Force progress display even when not on a TTY
        creator_url
    ]
    
    # Add any custom yt-dlp arguments if specified
    if 'ytdlp_args' in creator:
        logger.info(f"Using custom arguments for {creator['name']}: {creator['ytdlp_args']}")
        cmd.extend(creator['ytdlp_args'].split())
    
    logger.info(f"Starting download for {creator['name']}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    # Use Popen instead of run to capture output in real-time
    process = subprocess.Popen(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Make stdout non-blocking
    make_non_blocking(process.stdout.fileno())
    
    # Variables to track progress
    last_logged_percent = -1
    progress_pattern = re.compile(r'\[download\].*?(\d+\.\d)%')
    last_update_time = time.time()
    buffer = ""
    
    # Continue until process exits
    while process.poll() is None:
        try:
            # Try to read a chunk of output
            chunk = process.stdout.read(4096)
            if chunk:
                buffer += chunk
                lines = buffer.split('\n')
                buffer = lines.pop()  # Keep the last incomplete line in the buffer
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Always log download progress lines but throttle percentage updates
                    if line.startswith('[download]'):
                        current_time = time.time()
                        # Log important download messages immediately
                        if 'Destination:' in line or 'has already been downloaded' in line or 'Resuming download' in line:
                            logger.info(f"{creator['name']}: {line}")
                        # Handle progress lines with percentage - limit update frequency
                        elif '%' in line and (current_time - last_update_time >= 1.0):  # Max 1 update per second
                            match = progress_pattern.match(line)
                            if match:
                                current_percent = float(match.group(1))
                                logger.info(f"{creator['name']}: {line}")
                                last_logged_percent = current_percent
                                last_update_time = current_time
                    elif '[info]' in line:
                        logger.info(f"{creator['name']}: {line}")
                    elif 'has already been downloaded' in line:
                        logger.info(f"{creator['name']}: {line}")
                    elif 'Downloading page' in line:
                        logger.info(f"{creator['name']}: {line}")
                    else:
                        logger.debug(f"{creator['name']}: {line}")
        except (IOError, BlockingIOError):
            # No data available right now
            pass
        
        time.sleep(0.1)  # Small sleep to prevent CPU hogging
    
    # Process any remaining output
    remaining = process.stdout.read()
    if remaining:
        for line in remaining.splitlines():
            line = line.strip()
            if line:
                logger.info(f"{creator['name']}: {line}")
    
    process.stdout.close()
    return_code = process.wait()
    
    if return_code != 0:
        logger.error(f"Error downloading from {creator['name']} (return code: {return_code})")
        return False
    else:
        logger.info(f"Successfully completed processing {creator['name']}")
        return True

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
                download_success = download_creator(creator, archive_file, cookies_file, download_dir)
                
                # Only clean up files if downloads were successful
                if download_success:
                    logger.info(f"Cleaning up files for creator: {creator['name']}")
                    clean_up_files(download_dir, creator['name'])
                
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
