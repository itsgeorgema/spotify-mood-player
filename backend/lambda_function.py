import os
import sys
import json
import traceback

# Add current directory to path to ensure all local modules can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Heavy scientific/audio dependencies are loaded lazily inside the services that use them.
# Importing them here at cold-start would fail if the layer is missing or incompatible and
# also slows down the startup time. They will be imported where required (e.g. in
# lyrics_service.py). If an endpoint that needs them is hit without the layer attached,
# the request will raise an explicit ImportError at that time.

print("Lambda function initialized")

def lambda_handler(event, context):
    """Lambda handler for AWS Lambda that connects to the Flask app."""
    print(f"Lambda handler invoked with event: {event.get('path', 'unknown')}")
    
    try:
        # Special case for health endpoint for faster response
        if event.get('path') == '/api/health':
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': 'https://spotify-mood-player.vercel.app',
                    'Access-Control-Allow-Credentials': 'true',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent',
                    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
                },
                'body': json.dumps({
                    'status': 'healthy',
                    'message': 'API is running',
                    'timestamp': context.aws_request_id if context else 'local'
                })
            }
        
        # Import dependencies only when needed to avoid startup errors
        print("Importing Flask app...")
        from app import app
        import serverless_wsgi
        
        print("Processing request with Flask app...")
        # Use Flask app for all other endpoints
        response = serverless_wsgi.handle_request(app, event, context)
        
        # Flask handles CORS headers via @app.after_request - don't override them
        return response
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        traceback.print_exc()
        
        # Return a fallback response if there's an error
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://spotify-mood-player.vercel.app',
                'Access-Control-Allow-Credentials': 'true',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token,X-Amz-User-Agent',
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
            },
            'body': json.dumps({
                'status': 'error',
                'message': f'Lambda error: {str(e)}',
                'timestamp': context.aws_request_id if context else 'local'
            })
        } 