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

docker run -p 8501:8501 dftp-client:latest