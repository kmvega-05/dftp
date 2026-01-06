#!/bin/bash
# Quick test script to verify the Docker setup

set -e

echo "Building dFTP Client Docker image..."
docker build -t dftp-client:latest .

echo ""
echo "Build successful!"
echo ""
echo "To run the container:"
echo "  docker run -p 8501:8501 dftp-client:latest"
echo ""
echo "Then access at: http://localhost:8501"

docker run --net dftp_net -p 8501:8501 dftp-client:latest 

# docker run --rm --name data1 --net dftp_net -v $(pwd):/app dftp tests/run_data.py --id data1 --port 9000