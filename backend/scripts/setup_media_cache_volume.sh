#!/bin/bash
# Setup script for Fly.io media cache persistent volume
#
# This script creates a persistent volume for media cache storage on Fly.io
# Run this once before deploying the application

set -e

echo "Setting up Fly.io persistent volume for media cache..."

# Check if flyctl is installed
if ! command -v flyctl &> /dev/null; then
    echo "Error: flyctl is not installed. Please install it from https://fly.io/docs/getting-started/installing-flyctl/"
    exit 1
fi

# Get app name from fly.toml or use default
APP_NAME=$(grep -E '^app\s*=' fly.toml | sed 's/.*"\(.*\)".*/\1/' || echo "english-tutor")

echo "App name: $APP_NAME"

# Check if volume already exists
if flyctl volumes list -a "$APP_NAME" | grep -q "media_cache"; then
    echo "Volume 'media_cache' already exists. Skipping creation."
else
    echo "Creating persistent volume 'media_cache' (10GB)..."
    flyctl volumes create media_cache \
        --size 10 \
        --region lax \
        --app "$APP_NAME"
    echo "Volume created successfully!"
fi

echo ""
echo "Setup complete! The volume will be automatically mounted at /app/data when you deploy."
echo ""
echo "To verify the volume is attached, run:"
echo "  flyctl volumes list -a $APP_NAME"
