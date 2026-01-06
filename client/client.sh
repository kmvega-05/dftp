#!/bin/bash
# dFTP Client Docker runner - mounts source code in volume for hot reload
# Usage: ./client.sh [build|run|stop]

set -e

IMAGE_NAME="dftp-client:latest"
CONTAINER_NAME="dftp-client"
APP_PORT=8501

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_help() {
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  build       Build the Docker image"
    echo "  run         Run the container with volume mount (hot reload)"
    echo "  stop        Stop the running container"
    echo "  clean       Remove the image and container"
    echo "  rebuild     Rebuild image and run container"
    echo ""
    echo "Examples:"
    echo "  $0 build                    # Build image once"
    echo "  $0 run                      # Run with code mounted as volume"
    echo "  $0 stop                     # Stop the container"
    echo "  $0 rebuild                  # Clean rebuild and run"
}

build_image() {
    echo -e "${BLUE}Building dFTP Client Docker image...${NC}"
    docker build -t "$IMAGE_NAME" .
    echo -e "${GREEN}✓ Build successful!${NC}"
    echo ""
}

run_container() {
    # Check if container already running
    if docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${YELLOW}Container already running. Stop it first with: $0 stop${NC}"
        return
    fi

    echo -e "${BLUE}Starting dFTP Client container...${NC}"
    echo -e "${YELLOW}Code volume: $(pwd) → /home/app${NC}"
    echo ""
    
    # Run container with volume mount for live code reload
    docker run \
        --rm \
        --name "$CONTAINER_NAME" \
        --net dftp_net \
        -p "$APP_PORT:8501" \
        -v "$(pwd):/home/app" \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME"
}

stop_container() {
    if docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${BLUE}Stopping container...${NC}"
        docker stop "$CONTAINER_NAME"
        echo -e "${GREEN}✓ Container stopped${NC}"
    else
        echo -e "${YELLOW}Container not running${NC}"
    fi
}

clean_all() {
    echo -e "${BLUE}Cleaning up...${NC}"
    
    # Stop container if running
    if docker ps | grep -q "$CONTAINER_NAME"; then
        docker stop "$CONTAINER_NAME" 2>/dev/null || true
    fi
    
    # Remove image if exists
    if docker images | grep -q "$IMAGE_NAME"; then
        docker rmi "$IMAGE_NAME" 2>/dev/null || true
        echo -e "${GREEN}✓ Image removed${NC}"
    fi
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

main() {
    case "${1:-run}" in
        build)
            build_image
            echo -e "${GREEN}Next, run: $0 run${NC}"
            ;;
        run)
            if ! docker images | grep -q "$IMAGE_NAME"; then
                echo -e "${YELLOW}Image not found. Building first...${NC}"
                build_image
            fi
            run_container
            ;;
        stop)
            stop_container
            ;;
        clean)
            clean_all
            ;;
        rebuild)
            clean_all
            build_image
            run_container
            ;;
        help|-h|--help)
            print_help
            ;;
        *)
            echo "Unknown command: $1"
            echo ""
            print_help
            exit 1
            ;;
    esac
}

main "$@"
