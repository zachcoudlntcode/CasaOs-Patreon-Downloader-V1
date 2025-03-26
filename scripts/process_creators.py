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
import traceback

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

def sanitize_folder_name(name):
    """Create a clean folder name with no special characters"""
    # First, replace underscores with spaces
    cleaned = name.replace('_', ' ')
    
    # Remove special characters and replace with spaces
    cleaned = re.sub(r'[^\w\s-]', ' ', cleaned)
    
    # Replace multiple spaces with single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Trim spaces at beginning and end
    cleaned = cleaned.strip()
    
    # Format titles nicely - capitalize first letter of each word
    cleaned = ' '.join(word.capitalize() for word in cleaned.split())
    
    # Limit length to avoid path issues
    if len(cleaned) > 80:
        cleaned = cleaned[:77] + '...'
    
    # Don't convert spaces to underscores anymore
    # Keep the clean name with spaces
    
    return cleaned

def clean_up_files(download_dir, creator_name):
    """
    Clean up downloaded files:
    1. Create a dedicated folder for each video
    2. Add metadata from info files
    3. Keep thumbnails but remove other auxiliary files
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
        thumbnail_file = None
        other_files = []
        
        # Identify different file types
        for file_path, ext in group['files']:
            if ext.lower() in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
                video_file = file_path
            elif ext.lower() == '.info.json':
                info_json_file = file_path
            elif ext.lower() == '.description':
                description_file = file_path
            elif ext.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                thumbnail_file = file_path
            else:
                other_files.append(file_path)
        
        # Only proceed if we have a video file
        if video_file:
            # Create clean folder name from video title
            clean_title = sanitize_folder_name(base_name)
            video_folder = os.path.join(creator_dir, clean_title)
            
            # Create folder if it doesn't exist
            os.makedirs(video_folder, exist_ok=True)
            
            # Get video extension
            video_ext = os.path.splitext(video_file)[1]
            new_video_path = os.path.join(video_folder, f"video{video_ext}")
            
            # Add metadata if we have the necessary files
            if info_json_file:
                add_metadata_to_video(video_file, info_json_file, description_file)
            
            # Move the video file to its new location
            logger.info(f"Moving video to {new_video_path}")
            shutil.move(video_file, new_video_path)
            
            # Move the thumbnail file if we have one
            if thumbnail_file:
                thumb_ext = os.path.splitext(thumbnail_file)[1]
                new_thumb_path = os.path.join(video_folder, f"thumbnail{thumb_ext}")
                logger.info(f"Moving thumbnail to {new_thumb_path}")
                shutil.move(thumbnail_file, new_thumb_path)
            
            # Delete other files
            for file_to_delete in [info_json_file, description_file] + other_files:
                if file_to_delete and os.path.exists(file_to_delete):
                    logger.debug(f"Deleting extra file: {os.path.basename(file_to_delete)}")
                    os.remove(file_to_delete)

def verify_downloads(creator_dir):
    """Verify that video files were actually downloaded"""
    video_files = []
    for ext in ['.mp4', '.mkv', '.webm', '.mov', '.avi']:
        video_files.extend(glob.glob(os.path.join(creator_dir, f'*{ext}')))
    
    if not video_files:
        logger.warning(f"No video files found in {creator_dir}, only thumbnails/images may have been downloaded")
        return False
    
    logger.info(f"Found {len(video_files)} video files in {creator_dir}")
    return True

def attempt_alternative_download(creator, cookies_file, download_dir):
    """Try alternative download methods if standard method fails"""
    creator_name = creator['name']
    creator_dir = os.path.join(download_dir, creator_name)
    creator_url = f"https://www.patreon.com/{creator_name}/posts"
    output_template = os.path.join(creator_dir, 'alt_download_%(title)s.%(ext)s')
    
    logger.info(f"Attempting alternative download method for {creator_name}")
    
    # Create a test file with specific Patreon post URL instead of the creator's page
    alternative_cmd = [
        'yt-dlp',
        '--cookies', cookies_file,
        '-o', output_template,
        '--verbose',
        '--format', 'best',
        '--list-formats',  # Just list formats without downloading
        creator_url
    ]
    
    try:
        logger.info(f"Running diagnostic test for {creator_name}")
        # Add timeout to prevent freezing
        diagnostic_output = subprocess.run(
            alternative_cmd, 
            capture_output=True, 
            text=True, 
            check=False,
            timeout=60  # 60 second timeout to prevent hanging
        )
        
        # Log the output for debugging
        diagnostic_log = os.path.join(download_dir, 'logs', f"{creator_name}_diagnostic.log")
        with open(diagnostic_log, 'w') as f:
            f.write(f"STDOUT:\n{diagnostic_output.stdout}\n\nSTDERR:\n{diagnostic_output.stderr}")
        
        logger.info(f"Diagnostic information saved to {diagnostic_log}")
        
        # Check if we can see any video formats in the output
        if "video only" in diagnostic_output.stdout or "video+audio" in diagnostic_output.stdout:
            logger.info(f"Video formats detected for {creator_name}, but download failed. Check diagnostic log.")
            return True
        else:
            logger.warning(f"No video formats detected for {creator_name}. Posts may not contain videos.")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"Diagnostic timed out after 60 seconds for {creator_name}")
        return False
    except Exception as e:
        logger.error(f"Error during alternative download attempt: {str(e)}")
        return False

def get_ytdlp_version():
    """Get the installed version of yt-dlp"""
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True, check=True)
        version = result.stdout.strip()
        logger.info(f"Using yt-dlp version: {version}")
        return version
    except Exception as e:
        logger.warning(f"Could not determine yt-dlp version: {str(e)}")
        return "unknown"

def download_creator(creator, archive_file, cookies_file, download_dir):
    """Download content from a specific creator"""
    
    creator_url = f"https://www.patreon.com/{creator['name']}/posts"
    output_template = os.path.join(download_dir, creator['name'], '%(title)s [%(id)s].%(ext)s')
    
    days_back = creator.get('days_back', 30)
    date_after = (datetime.datetime.now() - datetime.timedelta(days=days_back)).strftime("%Y%m%d")
    
    logger.info(f"Processing creator: {creator['name']} (looking back {days_back} days)")
    
    # Check yt-dlp version to determine which options are supported
    ytdlp_version = get_ytdlp_version()
    
    # Modify yt-dlp command to better handle Patreon videos
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
        '--verbose',                # Add verbose output for better error diagnostics
        # Use better format selection instead of just 'best'
        '-f', 'bestvideo+bestaudio/best', # Try to get best video+audio separately and merge, fall back to best combined format
        '--merge-output-format', 'mp4', # Try to merge formats to mp4
        '--add-header', f'Referer:https://www.patreon.com/', # Add referer header for authentication
        '--ignore-errors',          # Continue on download errors
        '--geo-bypass',             # Try to bypass geo-restrictions
        '--no-overwrites',          # Don't overwrite files
        '--no-playlist',            # Treat as single post, not playlist
        '--playlist-end', '10',     # Limit to the 10 most recent posts
        creator_url
    ]
    
    # Remove problematic extract-audio option - by default yt-dlp will NOT extract audio only
    # if ytdlp_version != "unknown" and not ytdlp_version.startswith("2021"):
    #     cmd.extend(['--no-extract-audio'])  # This option is not supported
    
    # Add any custom yt-dlp arguments if specified
    if 'ytdlp_args' in creator:
        logger.info(f"Using custom arguments for {creator['name']}: {creator['ytdlp_args']}")
        ytdlp_args = creator['ytdlp_args'].split()
        
        # Don't duplicate verbose flag if it's already specified in custom args
        if '--verbose' in ytdlp_args and '--verbose' in cmd:
            cmd.remove('--verbose')
            
        cmd.extend(ytdlp_args)
    
    logger.info(f"Starting download for {creator['name']}")
    logger.info(f"Command: {' '.join(cmd)}")
    
    # Create a log file specifically for this creator's errors
    error_log_path = os.path.join(download_dir, 'logs', f"{creator['name']}_errors.log")
    os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
    
    # Check validity of cookies file
    if not os.path.isfile(cookies_file) or os.path.getsize(cookies_file) == 0:
        logger.error(f"Cookies file is missing or empty: {cookies_file}")
        with open(error_log_path, 'a') as f:
            f.write(f"{datetime.datetime.now()} - ERROR: Cookies file is missing or empty\n")
        return False
    
    # Check archive file access
    try:
        with open(archive_file, 'a') as f:
            pass  # Just testing we can write to it
    except Exception as e:
        logger.error(f"Cannot write to archive file: {str(e)}")
        with open(error_log_path, 'a') as f:
            f.write(f"{datetime.datetime.now()} - ERROR: Cannot write to archive file: {str(e)}\n")
        return False
    
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
    error_lines = []
    
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
                    
                    # Capture error lines for detailed reporting
                    if 'ERROR:' in line or 'error:' in line.lower() or 'warning:' in line.lower():
                        error_lines.append(line)
                        logger.error(f"{creator['name']}: {line}")
                        with open(error_log_path, 'a') as f:
                            f.write(f"{datetime.datetime.now()} - {line}\n")
                    
                    # Always log download progress lines but throttle percentage updates
                    elif line.startswith('[download]'):
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
        except Exception as e:
            # Log other exceptions during output processing
            logger.error(f"Error processing output for {creator['name']}: {str(e)}")
            logger.error(traceback.format_exc())
        
        time.sleep(0.1)  # Small sleep to prevent CPU hogging
    
    # Process any remaining output
    try:
        remaining = process.stdout.read()
        if remaining:
            for line in remaining.splitlines():
                line = line.strip()
                if not line:
                    continue
                    
                # Capture error lines for detailed reporting
                if 'ERROR:' in line or 'error:' in line.lower() or 'warning:' in line.lower():
                    error_lines.append(line)
                    logger.error(f"{creator['name']}: {line}")
                    with open(error_log_path, 'a') as f:
                        f.write(f"{datetime.datetime.now()} - {line}\n")
                else:
                    logger.info(f"{creator['name']}: {line}")
    except Exception as e:
        logger.error(f"Error processing final output for {creator['name']}: {str(e)}")
    
    process.stdout.close()
    return_code = process.wait()
    
    # Check if all errors are just "No supported media" errors, which are normal for text-only posts
    media_not_found_errors = [line for line in error_lines if "No supported media found in this post" in line]
    critical_errors = [line for line in error_lines if "No supported media found in this post" not in line]
    
    # Only consider it a failure if there are critical errors beyond just "no media" messages
    if return_code != 0 and critical_errors:
        # Comprehensive error reporting
        error_summary = "\n".join(error_lines[-10:]) if error_lines else "No specific error messages captured"
        logger.error(f"Error downloading from {creator['name']} (return code: {return_code})")
        logger.error(f"Error details for {creator['name']}:\n{error_summary}")
        
        # Check specific error conditions
        if any("HTTP Error 401" in line for line in error_lines):
            logger.error(f"Authentication failed for {creator['name']}. Please check your cookies.txt file.")
        elif any("HTTP Error 403" in line for line in error_lines):
            logger.error(f"Access forbidden for {creator['name']}. You may not have access to this content or your cookies expired.")
        elif any("HTTP Error 404" in line for line in error_lines):
            logger.error(f"Content not found for {creator['name']}. The URL might be incorrect or content removed.")
        elif any("Unable to extract" in line for line in error_lines):
            logger.error(f"Unable to extract content from {creator['name']}. Patreon layout might have changed.")
        
        # Write a detailed error report
        with open(error_log_path, 'a') as f:
            f.write(f"\n===== ERROR SUMMARY =====\n")
            f.write(f"Time: {datetime.datetime.now()}\n")
            f.write(f"Return code: {return_code}\n")
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Error details:\n")
            for line in error_lines:
                f.write(f"  {line}\n")
        
        # Add diagnostic attempt
        logger.info(f"Running diagnostics for {creator['name']} to determine cause of failure")
        attempt_alternative_download(creator, cookies_file, download_dir)
        
        return False
    elif media_not_found_errors and return_code != 0:
        # We only had "No supported media" errors, which is normal for text-only posts
        logger.info(f"No downloadable media found in {len(media_not_found_errors)} posts for {creator['name']}")
        logger.info(f"This is normal for text-only posts without attachments")
        return True
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
                
                # Verify that video files were downloaded, not just thumbnails
                if download_success:
                    video_files_found = verify_downloads(creator_dir)
                    if not video_files_found:
                        logger.warning(f"Only non-video files were downloaded for {creator['name']}. This might indicate:")
                        logger.warning("1. The Patreon posts don't contain videos")
                        logger.warning("2. Authentication/cookies issues preventing access to video content")
                        logger.warning("3. Patreon may have changed their site structure")
                        logger.warning("Try manually visiting the creator's page to verify content type")
                    else:
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
