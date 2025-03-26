#!/usr/bin/env python3
import subprocess
import sys
import json
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ytdlp_checker')

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

def get_ytdlp_help():
    """Get the help output of yt-dlp to check supported options"""
    try:
        result = subprocess.run(['yt-dlp', '--help'], capture_output=True, text=True, check=True)
        return result.stdout
    except Exception as e:
        logger.error(f"Error getting yt-dlp help: {str(e)}")
        return ""

def check_option_support(option):
    """Check if a specific option is supported in the current yt-dlp version"""
    help_text = get_ytdlp_help()
    return option in help_text

def main():
    """Run compatibility checks and report findings"""
    logger.info("Checking yt-dlp compatibility...")
    
    version = get_ytdlp_version()
    
    # Options to check
    options_to_check = [
        '--force-progress',
        '--no-extract-audio',
        '--extract-audio',
        '--no-progress-template',
        '--progress-template',
        '--add-header'
    ]
    
    compatibility_report = {
        "version": version,
        "supported_options": {},
        "unsupported_options": {}
    }
    
    for option in options_to_check:
        is_supported = check_option_support(option)
        if is_supported:
            compatibility_report["supported_options"][option] = True
            logger.info(f"Option {option} is supported")
        else:
            compatibility_report["unsupported_options"][option] = False
            logger.warning(f"Option {option} is NOT supported")
    
    # Write report to file
    report_path = "/downloads/ytdlp_compatibility.json"
    with open(report_path, 'w') as f:
        json.dump(compatibility_report, f, indent=2)
    
    logger.info(f"Compatibility report written to {report_path}")
    
    # Provide recommended command-line options
    logger.info("Recommended yt-dlp command-line options for this version:")
    cmd = ['yt-dlp', '--cookies', 'COOKIES_FILE', '--download-archive', 'ARCHIVE_FILE']
    
    # Add supported options
    for option in compatibility_report["supported_options"]:
        if option == '--add-header':
            cmd.extend(['--add-header', 'Referer:https://www.patreon.com/'])
        elif option in ['--progress-template', '--no-progress-template']:
            # Skip these as they're more complex
            pass
        else:
            cmd.append(option)
    
    logger.info(" ".join(cmd))
    return 0

if __name__ == "__main__":
    sys.exit(main())
