#!/bin/bash
set -e

# Default values
REGISTRY="docker.io"
USERNAME=""
IMAGE_NAME="youtube-updater-tg-bot"
TAG="latest"
DRY_RUN=false

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

Push Docker image to Docker Hub

OPTIONS:
    -u, --username USERNAME     Docker Hub username (required)
    -n, --name NAME            Image name (default: $IMAGE_NAME)
    -t, --tag TAG              Image tag (default: $TAG)
    -r, --registry REGISTRY    Registry URL (default: $REGISTRY)
    --dry-run                  Show what would be done without executing
    -h, --help                 Show this help

ENVIRONMENT VARIABLES:
    DOCKERHUB_USERNAME         Docker Hub username
    DOCKERHUB_TOKEN           Docker Hub access token (for login)

EXAMPLES:
    $0 -u myusername                           # Push with username
    $0 -u myusername -t v1.0.0                # Push specific tag
    $0 --username myusername --dry-run        # Show what would be done

    # Using environment variables:
    export DOCKERHUB_USERNAME=myusername
    export DOCKERHUB_TOKEN=my_token
    $0                                         # Push using env vars

NOTES:
    - You need to be logged into Docker Hub: docker login
    - Or set DOCKERHUB_TOKEN environment variable for automatic login
    - Image must exist locally or be built first

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
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

# Use environment variable if username not provided
if [[ -z "$USERNAME" && -n "$DOCKERHUB_USERNAME" ]]; then
    USERNAME="$DOCKERHUB_USERNAME"
fi

# Validate required parameters
if [[ -z "$USERNAME" ]]; then
    echo -e "${RED}❌ Username is required. Use -u/--username or set DOCKERHUB_USERNAME${NC}"
    show_help
    exit 1
fi

# Set image names
LOCAL_IMAGE="$IMAGE_NAME:$TAG"
REMOTE_IMAGE="$REGISTRY/$USERNAME/$IMAGE_NAME:$TAG"

echo -e "${BLUE}🐳 Docker Push Configuration${NC}"
echo -e "${YELLOW}Registry:${NC} $REGISTRY"
echo -e "${YELLOW}Username:${NC} $USERNAME"
echo -e "${YELLOW}Local image:${NC} $LOCAL_IMAGE"
echo -e "${YELLOW}Remote image:${NC} $REMOTE_IMAGE"
echo -e "${YELLOW}Dry run:${NC} $DRY_RUN"
echo

# Check if local image exists
if ! docker image inspect "$LOCAL_IMAGE" >/dev/null 2>&1; then
    echo -e "${RED}❌ Local image '$LOCAL_IMAGE' not found${NC}"
    echo -e "${YELLOW}💡 Build the image first with: ./scripts/docker-build.sh -t $TAG${NC}"
    exit 1
fi

# Login if token is provided
if [[ -n "$DOCKERHUB_TOKEN" ]]; then
    echo -e "${BLUE}🔐 Logging into Docker Hub...${NC}"
    if [[ "$DRY_RUN" == "false" ]]; then
        echo "$DOCKERHUB_TOKEN" | docker login "$REGISTRY" -u "$USERNAME" --password-stdin
        echo -e "${GREEN}✅ Logged in successfully${NC}"
    else
        echo -e "${YELLOW}[DRY RUN] Would login to $REGISTRY as $USERNAME${NC}"
    fi
    echo
fi

# Tag the image
echo -e "${BLUE}🏷️ Tagging image...${NC}"
TAG_CMD="docker tag $LOCAL_IMAGE $REMOTE_IMAGE"
echo "$TAG_CMD"

if [[ "$DRY_RUN" == "false" ]]; then
    if eval $TAG_CMD; then
        echo -e "${GREEN}✅ Tagged successfully${NC}"
    else
        echo -e "${RED}❌ Failed to tag image${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would tag image${NC}"
fi

echo

# Push the image
echo -e "${BLUE}🚀 Pushing image to Docker Hub...${NC}"
PUSH_CMD="docker push $REMOTE_IMAGE"
echo "$PUSH_CMD"

if [[ "$DRY_RUN" == "false" ]]; then
    if eval $PUSH_CMD; then
        echo
        echo -e "${GREEN}✅ Push completed successfully!${NC}"
        echo -e "${GREEN}🎉 Image available at: $REMOTE_IMAGE${NC}"
        echo
        echo -e "${BLUE}📋 To pull this image:${NC}"
        echo "   docker pull $REMOTE_IMAGE"
        echo
        echo -e "${BLUE}📋 To run this image:${NC}"
        echo "   docker run --env-file .env -p 8000:8000 $REMOTE_IMAGE"
    else
        echo -e "${RED}❌ Push failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[DRY RUN] Would push image to Docker Hub${NC}"
    echo -e "${YELLOW}[DRY RUN] Image would be available at: $REMOTE_IMAGE${NC}"
fi

# Logout if we logged in
if [[ -n "$DOCKERHUB_TOKEN" && "$DRY_RUN" == "false" ]]; then
    echo -e "${BLUE}🔓 Logging out...${NC}"
    docker logout "$REGISTRY"
fi