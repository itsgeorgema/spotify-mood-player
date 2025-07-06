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

# Get the API Gateway URL from the deployment
API_GATEWAY_URL=$(serverless info --verbose | grep -E "ServiceEndpoint|endpoint" | sed 's/.*: //')

echo "Deployment completed successfully!"
echo "API Gateway URL: $API_GATEWAY_URL"

# Instructions for updating the redirect URI in Spotify Developer Dashboard
echo ""
echo "IMPORTANT: Update your Spotify App settings AND AWS Parameter Store:"
echo "1. Go to https://developer.spotify.com/dashboard"
echo "2. Select your app"
echo "3. Click 'Edit Settings'"
echo "4. Add this Redirect URI: ${API_GATEWAY_URL}/api/callback"
echo "5. Save changes"
echo ""
echo "6. Update AWS Parameter Store with the redirect URI:"
echo "   aws ssm put-parameter --name '/spotify-mood-player/prod/SPOTIPY_REDIRECT_URI' --value '${API_GATEWAY_URL}/api/callback' --type 'String' --overwrite"
echo ""
echo "7. Then redeploy to pick up the new redirect URI:"
echo "   serverless deploy" 