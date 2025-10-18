#!/bin/bash
set -e

# Default values
IMAGE_NAME="youtube-updater-tg-bot"
TAG="latest"
PLATFORM="linux/amd64,linux/arm64"
BUILD_ARGS=""
PUSH=false
LOAD=true

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

Build Docker image for YouTube Updater Telegram Bot

OPTIONS:
    -n, --name NAME         Image name (default: $IMAGE_NAME)
    -t, --tag TAG           Image tag (default: $TAG)
    -p, --platform PLATFORM Platform(s) to build for (default: $PLATFORM)
    --push                  Push to registry (disables --load)
    --no-load               Don't load image to local Docker
    --build-arg ARG=VALUE   Pass build argument
    --cache-from TYPE=REF   Cache source (e.g., type=gha)
    --cache-to TYPE=REF     Cache destination (e.g., type=gha)
    -h, --help              Show this help

EXAMPLES:
    $0                                          # Build with defaults
    $0 -t v1.0.0                               # Build with specific tag
    $0 --push -t latest                        # Build and push to registry
    $0 -p linux/amd64                         # Build for single platform
    $0 --build-arg WEBHOOK_PORT=9000          # Pass build argument

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -p|--platform)
            PLATFORM="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            LOAD=false
            shift
            ;;
        --no-load)
            LOAD=false
            shift
            ;;
        --build-arg)
            BUILD_ARGS="$BUILD_ARGS --build-arg $2"
            shift 2
            ;;
        --cache-from)
            CACHE_FROM="--cache-from $2"
            shift 2
            ;;
        --cache-to)
            CACHE_TO="--cache-to $2"
            shift 2
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
if [[ "$IMAGE_NAME" != *"/"* ]]; then
    FULL_IMAGE_NAME="$IMAGE_NAME:$TAG"
else
    FULL_IMAGE_NAME="$IMAGE_NAME:$TAG"
fi

echo -e "${BLUE}🐳 Building Docker image${NC}"
echo -e "${YELLOW}Image:${NC} $FULL_IMAGE_NAME"
echo -e "${YELLOW}Platform(s):${NC} $PLATFORM"
echo -e "${YELLOW}Push:${NC} $PUSH"
echo -e "${YELLOW}Load:${NC} $LOAD"

# Check if Docker Buildx is available
if ! docker buildx version >/dev/null 2>&1; then
    echo -e "${RED}❌ Docker Buildx is required but not available${NC}"
    exit 1
fi

# Create builder instance if needed
BUILDER_NAME="youtube-bot-builder"
if ! docker buildx inspect $BUILDER_NAME >/dev/null 2>&1; then
    echo -e "${BLUE}🔧 Creating buildx builder: $BUILDER_NAME${NC}"
    docker buildx create --name $BUILDER_NAME --use
fi

# Use the builder
docker buildx use $BUILDER_NAME

# Build the image
BUILD_CMD="docker buildx build"
BUILD_CMD="$BUILD_CMD --platform $PLATFORM"
BUILD_CMD="$BUILD_CMD -t $FULL_IMAGE_NAME"
BUILD_CMD="$BUILD_CMD $BUILD_ARGS"

if [[ "$CACHE_FROM" ]]; then
    BUILD_CMD="$BUILD_CMD $CACHE_FROM"
fi

if [[ "$CACHE_TO" ]]; then
    BUILD_CMD="$BUILD_CMD $CACHE_TO"
fi

if [[ "$PUSH" == "true" ]]; then
    BUILD_CMD="$BUILD_CMD --push"
elif [[ "$LOAD" == "true" ]]; then
    BUILD_CMD="$BUILD_CMD --load"
fi

BUILD_CMD="$BUILD_CMD -f deployment/docker/Dockerfile ."

echo -e "${BLUE}🔨 Running build command:${NC}"
echo "$BUILD_CMD"
echo

# Execute the build
if eval $BUILD_CMD; then
    echo
    echo -e "${GREEN}✅ Build completed successfully!${NC}"

    if [[ "$LOAD" == "true" && "$PUSH" == "false" ]]; then
        echo -e "${GREEN}📦 Image loaded to local Docker: $FULL_IMAGE_NAME${NC}"
    fi

    if [[ "$PUSH" == "true" ]]; then
        echo -e "${GREEN}🚀 Image pushed to registry: $FULL_IMAGE_NAME${NC}"
    fi
else
    echo -e "${RED}❌ Build failed!${NC}"
    exit 1
fi