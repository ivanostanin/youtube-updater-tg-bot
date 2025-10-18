#!/bin/bash
set -e

# Default values
IMAGE_NAME="youtube-updater-tg-bot"
TAG="latest"
CONTAINER_NAME="youtube-updater-tg-bot"
ENV_FILE=".env"
PORT="8000"
DETACH=false
REMOVE=true
INTERACTIVE=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Run Docker container for YouTube Updater Telegram Bot

OPTIONS:
    -i, --image IMAGE          Image name (default: $IMAGE_NAME:$TAG)
    -t, --tag TAG             Image tag (default: $TAG)
    -n, --name NAME           Container name (default: $CONTAINER_NAME)
    -e, --env-file FILE       Environment file (default: $ENV_FILE)
    -p, --port PORT           Host port mapping (default: $PORT)
    -d, --detach              Run in background
    --no-rm                   Don't remove container on exit
    --interactive             Run with interactive shell
    -h, --help                Show this help

EXAMPLES:
    $0                                    # Run with defaults
    $0 -d                                # Run in background
    $0 -p 9000                          # Use different port
    $0 -e .env.production               # Use different env file
    $0 --interactive                    # Run with shell access
    $0 -i myusername/youtube-bot:v1.0.0 # Run specific image

NOTES:
    - Environment file must exist (default: .env)
    - Container will be removed after stopping (use --no-rm to keep)
    - Use Ctrl+C to stop the container when running in foreground

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--image)
            if [[ "$2" == *":"* ]]; then
                IMAGE_NAME="${2%:*}"
                TAG="${2#*:}"
            else
                IMAGE_NAME="$2"
            fi
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        -d|--detach)
            DETACH=true
            shift
            ;;
        --no-rm)
            REMOVE=false
            shift
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Set full image name
FULL_IMAGE_NAME="$IMAGE_NAME:$TAG"

# Validate environment file
if [[ ! -f "$ENV_FILE" ]]; then
    echo -e "${RED}❌ Environment file '$ENV_FILE' not found${NC}"
    echo -e "${YELLOW}💡 Create it from template: cp .env.example $ENV_FILE${NC}"
    exit 1
fi

# Check if image exists
if ! docker image inspect "$FULL_IMAGE_NAME" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️ Image '$FULL_IMAGE_NAME' not found locally${NC}"
    echo -e "${BLUE}🔍 Attempting to pull from registry...${NC}"
    if ! docker pull "$FULL_IMAGE_NAME"; then
        echo -e "${RED}❌ Failed to pull image${NC}"
        echo -e "${YELLOW}💡 Build the image first with: ./scripts/docker-build.sh -t $TAG${NC}"
        exit 1
    fi
fi

# Stop and remove existing container if it exists
if docker ps -a --format "table {{.Names}}" | grep -q "^$CONTAINER_NAME$"; then
    echo -e "${YELLOW}🛑 Stopping existing container: $CONTAINER_NAME${NC}"
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
fi

echo -e "${BLUE}🐳 Starting Docker container${NC}"
echo -e "${YELLOW}Image:${NC} $FULL_IMAGE_NAME"
echo -e "${YELLOW}Container:${NC} $CONTAINER_NAME"
echo -e "${YELLOW}Port:${NC} $PORT:8000"
echo -e "${YELLOW}Env file:${NC} $ENV_FILE"
echo -e "${YELLOW}Detached:${NC} $DETACH"
echo -e "${YELLOW}Remove on exit:${NC} $REMOVE"
echo

# Build docker run command
RUN_CMD="docker run"
RUN_CMD="$RUN_CMD --name $CONTAINER_NAME"
RUN_CMD="$RUN_CMD --env-file $ENV_FILE"
RUN_CMD="$RUN_CMD -p $PORT:8000"

if [[ "$REMOVE" == "true" ]]; then
    RUN_CMD="$RUN_CMD --rm"
fi

if [[ "$DETACH" == "true" ]]; then
    RUN_CMD="$RUN_CMD -d"
fi

if [[ "$INTERACTIVE" == "true" ]]; then
    RUN_CMD="$RUN_CMD -it --entrypoint /bin/bash"
    FULL_IMAGE_NAME="$FULL_IMAGE_NAME"
else
    FULL_IMAGE_NAME="$FULL_IMAGE_NAME"
fi

RUN_CMD="$RUN_CMD $FULL_IMAGE_NAME"

echo -e "${BLUE}🚀 Running command:${NC}"
echo "$RUN_CMD"
echo

# Execute the run command
if [[ "$DETACH" == "true" ]]; then
    if CONTAINER_ID=$(eval $RUN_CMD); then
        echo -e "${GREEN}✅ Container started successfully!${NC}"
        echo -e "${GREEN}📋 Container ID: $CONTAINER_ID${NC}"
        echo
        echo -e "${BLUE}📋 Useful commands:${NC}"
        echo "   docker logs $CONTAINER_NAME          # View logs"
        echo "   docker logs -f $CONTAINER_NAME       # Follow logs"
        echo "   docker stop $CONTAINER_NAME          # Stop container"
        echo "   docker exec -it $CONTAINER_NAME bash # Access container"
        echo
        echo -e "${BLUE}🌐 Bot should be available at:${NC}"
        echo "   http://localhost:$PORT/health        # Health check"
    else
        echo -e "${RED}❌ Failed to start container${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}Press Ctrl+C to stop the container${NC}"
    echo
    eval $RUN_CMD
fi