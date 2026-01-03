#!/usr/bin/env python3
"""
Docker Entrypoint Script for dFTP Client

This is the single entry point for the Docker container.
It initializes the environment and starts the Streamlit FTP client UI.

No additional scripts or configuration needed - just run this script from Docker.
"""

import sys
import os
import subprocess
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dFTP-Client")

FAST_START = os.getenv('CLIENT_FAST_START', '0').lower() in ('1', 'true', 'yes')

def setup_environment():
    """
    Setup Python environment and project paths.
    Ensures all imports work correctly from within the container.
    """
    logger.info("Setting up environment...")
    
    # Get the working directory (should be /home/app in Docker)
    app_root = os.getcwd()
    
    # Ensure the app root is in Python's path
    if app_root not in sys.path:
        sys.path.insert(0, app_root)
        logger.info(f"Added {app_root} to Python path")
    
    # Set Python environment variables for optimal container performance
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'  # Don't create .pyc files
    os.environ['PYTHONUNBUFFERED'] = '1'           # Unbuffered output
    os.environ['STREAMLIT_TELEMETRY_ENABLED'] = 'false'  # Disable Streamlit telemetry
    
    logger.info("Environment setup complete")


def verify_dependencies():
    """
    Verify that all required Python modules are available.
    This helps catch missing dependencies early.
    """
    logger.info("Verifying dependencies...")

    if FAST_START:
        logger.info("FAST_START enabled — skipping dependency verification")
        return True

    required_modules = ['streamlit', 'socket', 'threading']

    for module in required_modules:
        try:
            __import__(module)
            logger.info(f"✓ {module} available")
        except ImportError:
            logger.error(f"✗ Missing required module: {module}")
            logger.error(f"  Install it with: pip install {module}")
            return False

    logger.info("All dependencies verified")
    return True


def verify_project_structure():
    """
    Verify that the expected project structure exists.
    This ensures the container has all necessary files.
    """
    logger.info("Verifying project structure...")

    if FAST_START:
        logger.info("FAST_START enabled — skipping project structure verification")
        return True

    required_files = [
        'ui/app.py',
        'core/__init__.py',
        'core/connection.py',
        'core/commands.py',
        'core/parser.py',
        'core/data_connection.py',
        'core/transfer.py'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
            logger.warning(f"✗ Missing file: {file_path}")
        else:
            logger.info(f"✓ Found {file_path}")
    
    if missing_files:
        logger.error(f"Missing {len(missing_files)} required files")
        return False
    
    logger.info("Project structure verified")
    return True


def start_streamlit_client(host='0.0.0.0', port=8501):
    """
    Start the Streamlit FTP client UI.
    
    Args:
        host: Host to bind Streamlit to (default: 0.0.0.0 for Docker)
        port: Port to expose Streamlit on (default: 8501)
    """
    logger.info(f"Starting Streamlit FTP Client UI on {host}:{port}...")
    
    cmd = [
        'streamlit',
        'run',
        'ui/app.py',
        f'--server.port={port}',
        f'--server.address={host}',
        '--logger.level=info',
        '--client.showErrorDetails=true'
    ]

    # Replace the current process with the Streamlit process for faster startup and proper signal handling
    try:
        os.execvp(cmd[0], cmd)
    except Exception as e:
        logger.error(f"Failed to exec Streamlit: {e}")
        # Fallback to subprocess.run for better diagnostics
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e2:
            logger.error(f"Streamlit exited with error code {e2.returncode}")
            sys.exit(e2.returncode)
        except Exception as e2:
            logger.error(f"Failed to start Streamlit: {e2}")
            sys.exit(1)


def main():
    """
    Main entry point for the Docker container.
    Performs all necessary setup and starts the client.
    """
    logger.info("=" * 70)
    logger.info("dFTP Client Container Startup")
    logger.info("=" * 70)
    
    # Step 1: Setup environment
    setup_environment()
    
    # Step 2: Verify dependencies (skipped if FAST_START enabled)
    if not verify_dependencies():
        logger.error("Dependency verification failed")
        sys.exit(1)

    # Step 3: Verify project structure (skipped if FAST_START enabled)
    if not verify_project_structure():
        logger.error("Project structure verification failed")
        sys.exit(1)
    
    # Step 4: Start the Streamlit client
    logger.info("=" * 70)
    logger.info("All checks passed. Starting client...")
    logger.info("=" * 70)
    start_streamlit_client()


if __name__ == '__main__':
    main()
