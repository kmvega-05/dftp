# dFTP Client Docker Entrypoint

## Overview

The `entrypoint.py` script is the single point of entry for the Docker container. It replaces the need for multiple shell scripts and complex Docker configurations.

## What It Does

1. **Environment Setup**: Configures Python environment variables for optimal container performance
2. **Path Management**: Ensures all project imports resolve correctly
3. **Dependency Verification**: Checks that all required Python modules are installed
4. **Project Structure Validation**: Verifies that all expected files are present
5. **Client Startup**: Launches the Streamlit FTP client UI with proper configuration

## Building and Running

### Build the Docker image:
```bash
docker build -t dftp-client .
```

### Run the container:
```bash
docker run -p 8501:8501 dftp-client
```

### Run with custom settings:
```bash
docker run -p 8501:8501 -e STREAMLIT_TELEMETRY_ENABLED=false dftp-client
```

## Access the Client

Once running, access the Streamlit UI at:
```
http://localhost:8501
```

## Docker Compose Example

If you want to run this alongside the FTP server:

```yaml
version: '3.8'

services:
  dftp-client:
    build:
      context: ./client
      dockerfile: Dockerfile
    ports:
      - "8501:8501"
    environment:
      - STREAMLIT_TELEMETRY_ENABLED=false
    networks:
      - dftp-network

  dftp-server:
    build:
      context: ./server
      dockerfile: Dockerfile
    ports:
      - "2121:2121"
    networks:
      - dftp-network

networks:
  dftp-network:
    driver: bridge
```

## What Happens on Startup

1. Python path is configured to include the app root
2. All required modules (streamlit, socket, threading) are verified
3. Project files are checked (ui/app.py, core modules, etc.)
4. Streamlit server starts on 0.0.0.0:8501
5. Container logs show detailed startup information

## Logs

All startup information is logged with timestamps. Watch the Docker logs to see:
- Environment setup progress
- Dependency verification results
- Project structure validation
- Streamlit startup messages

## No Additional Configuration Needed

Everything is self-contained in the script:
- No separate startup scripts required
- No manual environment variable configuration needed
- No additional shell scripts to maintain
- All logic in a single, well-documented Python file
