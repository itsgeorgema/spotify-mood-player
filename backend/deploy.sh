#!/bin/bash
set -e

# Set deployment timestamp for unique service names
export DEPLOY_TIMESTAMP=$(date +%s)

echo "Starting deployment with timestamp: $DEPLOY_TIMESTAMP"

# Step 1: Deploy the layer first
echo "Deploying Lambda Layer..."
serverless deploy --config layer.yml --verbose

# Wait a moment for layer to be fully deployed
echo "Waiting for layer to be ready..."
sleep 10

# Step 2: Deploy the main function
echo "Deploying main Lambda function..."
serverless deploy --verbose