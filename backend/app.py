from dotenv import load_dotenv
import os
import sys # For flushing output
import traceback
from datetime import timedelta  
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import time
import spotify_service
from db import get_or_create_user, insert_tracks, get_tracks_by_mood, delete_tracks_for_user, get_db_connection, init_database_config, close_db_connection
import logging
import random
from migrations import run_migrations
import json
from lyrics_service import analyze_user_library, get_tracks_for_mood

# Set up logging
logging.basicConfig(
    level=logging.INFO if os.getenv('FLASK_ENV') == 'production' else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load .env from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Initialize PostgreSQL connection pool
print("--- Initializing database connection ---")
if os.getenv('SUPABASE_DATABASE_URL'):
    print("Using Supabase PostgreSQL database")
else:
    print("Using local PostgreSQL database")

# Retry database initialization a few times before giving up
max_init_retries = 5
init_retry_delay = 2  # seconds
init_success = False

for attempt in range(max_init_retries):
    try:
        # With new serverless approach, just initialize the config
        init_success = init_database_config()
        if init_success:
            print(f"--- Database configuration initialized successfully on attempt {attempt + 1}/{max_init_retries} ---")
            break
        else:
            print(f"--- Database configuration failed on attempt {attempt + 1}/{max_init_retries}, retrying... ---")
    except Exception as e:
        print(f"--- Database configuration error on attempt {attempt + 1}/{max_init_retries}: {e} ---")
        traceback.print_exc()
    
    if attempt < max_init_retries - 1:
        print(f"--- Waiting {init_retry_delay} seconds before next attempt ---")
        time.sleep(init_retry_delay)
        init_retry_delay = min(init_retry_delay * 2, 30)  # Exponential backoff, max 30 seconds

if not init_success:
    print("--- WARNING: Failed to initialize database configuration after multiple attempts. The app will continue but database features may not work. ---")
else:
    print("--- Database configuration initialized and ready ---")

# Run database migrations to ensure tables exist
if init_success:
    print("--- Running database migrations ---")
    try:
        run_migrations()
        print("--- Database migrations completed successfully ---")
    except Exception as e:
        print(f"--- Error running migrations: {e} ---")
        traceback.print_exc()
else:
    print("--- Skipping migrations since database configuration failed ---")

# No dotenv loading here; all env vars come from Docker Compose

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# --- Environment-Specific Configuration ---
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production'
IS_LAMBDA = os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None
backend_port_local_dev = os.getenv('PORT', '5001')

if IS_PRODUCTION and not IS_LAMBDA:
    fly_app_hostname = os.getenv('FLY_APP_HOSTNAME')
    if fly_app_hostname:
        app.config['SERVER_NAME'] = fly_app_hostname                                       
    else:
        # Fallback if FLY_APP_HOSTNAME isn't set
        app.config['SERVER_NAME'] = "https://mood-player-backend.fly.dev"

    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='None', # 'None' for cross-origin requests
        SESSION_COOKIE_PATH='/',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True
    )
    print(f"--- Flask SERVER_NAME (Production): {app.config.get('SERVER_NAME', 'Not Set')} ---")
elif not IS_LAMBDA: # Local development
    app.config['SERVER_NAME'] = f"127.0.0.1:{backend_port_local_dev}"
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Set True if tunneling
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax', #Set to 'None' if tunneling
        SESSION_COOKIE_PATH='/',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True
    )
    print(f"--- Flask SERVER_NAME (Development): {app.config['SERVER_NAME']} ---")
else: # Lambda deployment
    # Don't set SERVER_NAME for Lambda, let API Gateway handle it
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='None', # 'None' for cross-origin requests
        SESSION_COOKIE_PATH='/',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True
    )
    print("--- Running in AWS Lambda, no SERVER_NAME set ---")

print(f"--- Flask Session Cookie SAMESITE: {app.config['SESSION_COOKIE_SAMESITE']} ---")
print(f"--- Flask Session Cookie SECURE: {app.config['SESSION_COOKIE_SECURE']} ---")
print(f"--- Flask Session Cookie HTTPONLY: {app.config['SESSION_COOKIE_HTTPONLY']} ---")
print(f"--- Flask Session Cookie PATH: {app.config['SESSION_COOKIE_PATH']} ---")
if 'SESSION_COOKIE_DOMAIN' in app.config: # Print domain only if explicitly set
    print(f"--- Flask Session Cookie DOMAIN: {app.config.get('SESSION_COOKIE_DOMAIN')} ---")
sys.stdout.flush()

# CORS CONFIG
frontend_url_from_env = os.getenv("FRONTEND_URL") or "https://spotify-mood-player.vercel.app"
allowed_origins = [frontend_url_from_env, "https://spotify-mood-player.vercel.app"]

CORS(app, 
     resources={r"/api/*": {
         "origins": allowed_origins,
         "supports_credentials": True,
         "expose_headers": ["Set-Cookie", "Authorization"],
         "allow_headers": ["Content-Type", "Authorization", "cache-control", "Pragma"],
         "methods": ["GET", "POST", "OPTIONS"]
     }},
     supports_credentials=True)


# --- API Routes ---
@app.route('/api/login', methods=['GET'])
def login():
    print("--- /api/login route hit ---")
    try:
        auth_manager = spotify_service.create_spotify_oauth()
        auth_url = auth_manager.get_authorize_url()
        print(f"--- Redirect URI set to: {os.getenv('SPOTIPY_REDIRECT_URI')} ---")
        sys.stdout.flush()
        return redirect(auth_url)
    except Exception as e:
        print(f"--- Error in /api/login: {str(e)} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Failed to initialize Spotify login"}), 500

@app.route('/api/callback', methods=['GET'])
def spotify_callback():
    print("--- /api/callback route hit ---")
    sys.stdout.flush()
    try:
        auth_manager = spotify_service.create_spotify_oauth()
        code = request.args.get('code')
        
        if not code:
            print("--- /api/callback: No code provided ---")
            return redirect(f"{frontend_url_from_env}/?error=no_code")

        # Exchange authorization code for tokens
        token_info = auth_manager.get_access_token(code)

        print("--- Token stored in session successfully ---")
        
        # Store tokens in session with explicit session configuration
        session.permanent = True  # Make the session permanent
        session['spotify_token_info'] = token_info
        session.modified = True
        
        # Set explicit cookie parameters
        response = redirect(f"{frontend_url_from_env}/callback?login_success=true")
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        return response

    except Exception as e:
        print(f"--- Error in callback: {str(e)} ---")
        traceback.print_exc()
        return redirect(f"{frontend_url_from_env}/?error=auth_failed")

@app.route('/api/check_auth', methods=['GET'])
def check_auth_status():
    print("--- /api/check_auth route hit ---")
    print(f"--- /api/check_auth: Request cookies count: {len(request.cookies)} ---")
    sys.stdout.flush()
    
    token_info = session.get('spotify_token_info')
    if not token_info:
        print("--- No token_info in session ---")
        return jsonify({"isAuthenticated": False}), 200

    sp_client = spotify_service.get_spotify_client_from_session()
    if sp_client:
        print("--- User is authenticated with valid token ---")
        return jsonify({"isAuthenticated": True}), 200
    else:
        print("--- Token validation failed ---")
        return jsonify({"isAuthenticated": False}), 200

@app.route('/api/logout', methods=['POST'])
def spotify_logout():
    print("--- /api/logout route hit ---")
    sys.stdout.flush()
    
    sp = spotify_service.get_spotify_client_from_session()
    if sp:
        try:
            user_profile = sp.current_user()
            if user_profile:
                spotify_id = user_profile['id']
                # Use fresh connection for this operation (serverless pattern)
                try:
                    user_id = get_or_create_user(spotify_id)
                    delete_tracks_for_user(user_id)
                    print(f"--- Deleted tracks for user {user_id} on logout ---")
                except Exception as e:
                    logger.error(f"Error deleting tracks on logout: {e}")
                    print(f"--- Error deleting tracks on logout: {e} ---")
        except Exception as e:
            logger.error(f"Error in logout operation: {e}")
            print(f"--- Error in logout operation: {e} ---")
    
    # Always clear session data
    session.pop('spotify_token_info', None)
    session.pop('mood_uris', None)
    session.modified = True 
    print("--- User logged out, session data cleared. ---")
    sys.stdout.flush()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/api/analyze', methods=['POST'])
def analyze_library_route():
    """route to manually trigger library analysis"""
    print("--- /api/analyze route hit ---")
    sys.stdout.flush()
    
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        print("--- /api/analyze: User not authenticated ---")
        sys.stdout.flush()
        return jsonify({"error": "Not authenticated"}), 401

    try:
        user_profile = sp.current_user()
        if not user_profile:
            return jsonify({"error": "Could not fetch user profile from Spotify."}), 401
        spotify_id = user_profile['id']
        
        # Import analyze_user_library only when needed
        try:
            print("--- Starting library analysis, this may take a minute... ---")
            sys.stdout.flush()
            analyzed_tracks, mood_uris = analyze_user_library(sp, session)
            
            if not analyzed_tracks or not mood_uris:
                return jsonify({"error": "No tracks could be analyzed"}), 500
                
            # Store in database
            print(f"--- Storing {len(analyzed_tracks)} tracks in database ---")
            sys.stdout.flush()
            success = insert_tracks(spotify_id, analyzed_tracks)
            
            if not success:
                return jsonify({"error": "Failed to store tracks in database"}), 500
                
            # Store in session too (useful for serverless context where we might not have DB access)
            session['mood_uris'] = mood_uris
            session.modified = True
            
            print("--- Analysis complete ---")
            sys.stdout.flush()
            return jsonify({
                "success": True,
                "tracks_analyzed": len(analyzed_tracks),
                "moods": list(mood_uris.keys()) if mood_uris else []
            })
        except ImportError as e:
            print(f"--- Error importing lyrics_service: {e} ---")
            sys.stdout.flush()
            return jsonify({"error": f"Could not load lyrics analysis module: {str(e)}"}), 500
            
    except Exception as e:
        print(f"--- Error in /api/analyze: {e} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": str(e)}), 500

@app.route('/api/mood-tracks', methods=['GET'])
def get_mood_tracks_route():
    """Get tracks for a specific mood from the database"""
    print("--- /api/mood-tracks route hit ---")
    sys.stdout.flush()
    
    # Verify user authentication
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        logger.warning("User not authenticated in /api/mood-tracks")
        return jsonify({"error": "Not authenticated"}), 401
        
    # Get the requested mood
    mood = request.args.get('mood')
    if not mood:
        logger.warning("No mood specified in /api/mood-tracks")
        return jsonify({"error": "No mood specified"}), 400
    
    # First check if we have tracks in session (prioritize session for serverless context)
    session_mood_uris = session.get('mood_uris', {})
    if session_mood_uris and mood in session_mood_uris and len(session_mood_uris[mood]) > 0:
        # Return random selection if we have more than enough tracks
        tracks = session_mood_uris[mood]
        if len(tracks) > 20:
            tracks = random.sample(tracks, 20)
            
        print(f"--- Returning {len(tracks)} tracks for mood '{mood}' from session ---")
        sys.stdout.flush()
        return jsonify({"tracks": tracks})
    
    # If not in session, try database
    try:
        user_profile = sp.current_user()
        if user_profile and 'id' in user_profile:
            user_id = user_profile['id']
            tracks = get_tracks_by_mood(user_id, mood)
            
            if tracks and len(tracks) > 0:
                print(f"--- Returning {len(tracks)} tracks for mood '{mood}' from database ---")
                sys.stdout.flush()
                return jsonify({"tracks": tracks})
        else:
            print("--- User profile not available ---")
            sys.stdout.flush()
    except Exception as e:
        logger.error(f"Database error in get_mood_tracks_route: {e}")
        # Continue to fallback
    
    # If we still don't have tracks, try the fallback mood analysis
    try:
        print(f"--- No tracks found for mood '{mood}', attempting fallback mood analysis ---")
        sys.stdout.flush()
        
        # Get the user's library again
        try:
            analyzed_tracks, mood_uris = analyze_user_library(sp, session)
            
            # Store the results in session for future use
            if mood_uris:
                session['mood_uris'] = mood_uris
                session.modified = True
                
            # Get tracks for the requested mood
            if mood_uris and mood in mood_uris:
                tracks = mood_uris[mood]
                if len(tracks) > 20:
                    tracks = random.sample(tracks, 20)
                    
                print(f"--- Returning {len(tracks)} tracks for mood '{mood}' from fallback analysis ---")
                sys.stdout.flush()
                return jsonify({"tracks": tracks})
        except Exception as e:
            logger.error(f"Error in fallback analysis: {e}")
            traceback.print_exc()
    except ImportError as e:
        print(f"--- Error importing lyrics_service: {e} ---")
        sys.stdout.flush()
        
    # If we still don't have tracks, return empty list
    print(f"--- No tracks found for mood '{mood}' ---")
    sys.stdout.flush()
    return jsonify({"tracks": []})

@app.route('/api/play', methods=['POST'])
def play_tracks_route():
    """Play selected tracks on the specified Spotify device"""
    print("--- /api/play route hit ---")
    sys.stdout.flush()
    
    # Verify authentication
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        logger.error("User not authenticated in /api/play")
        return jsonify({"error": "Not authenticated"}), 401
    
    # Parse request data
    data = request.json or {}
    track_uris = data.get('track_uris')
    device_id = data.get('device_id')
    
    # Validate input
    if not track_uris:
        logger.warning("No tracks provided in /api/play")
        return jsonify({"error": "No tracks provided"}), 400
    
    if not device_id:
        logger.warning("No device ID provided in /api/play")
        return jsonify({
            "error": "No device selected. Please select a playback device in Spotify and try again."
        }), 400
    
    try:
        # Limit to 75 tracks max for better performance
        if len(track_uris) > 75:
            logger.info(f"Limiting playback from {len(track_uris)} tracks to 75")
            track_uris = track_uris[:75]
        
        # Start playback
        logger.info(f"Starting playback of {len(track_uris)} tracks on device {device_id}")
        sp.start_playback(device_id=device_id, uris=track_uris)
        
        return jsonify({
            "message": "Playback started",
            "track_count": len(track_uris),
            "device_id": device_id
        }), 200
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error starting playback: {error_message}")
        
        # Provide user-friendly error messages
        if "NO_ACTIVE_DEVICE" in error_message:
            return jsonify({
                "error": "The selected device is not active. Please make sure Spotify is open on your device."
            }), 400
        elif "PREMIUM_REQUIRED" in error_message:
            return jsonify({
                "error": "This feature requires Spotify Premium. Please upgrade your account to use this feature."
            }), 400
        
        return jsonify({
            "error": "Failed to start playback. Make sure your Spotify app is open and your selected device is active."
        }), 500

@app.route('/api/queue', methods=['POST'])
def queue_tracks_route():
    print("--- /api/queue route hit ---")
    sys.stdout.flush()
    data = request.get_json()
    track_uris = data.get('track_uris')
    device_id = data.get('device_id')

    if not track_uris:
        print("--- /api/queue: track_uris are required. ---")
        sys.stdout.flush()
        return jsonify({"error": "track_uris are required"}), 400

    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        print("--- /api/queue: User not authenticated. ---")
        sys.stdout.flush()
        return jsonify({"error": "User not authenticated or token expired. Please login."}), 401
    
    print(f"--- /api/queue: Attempting to queue {len(track_uris)} tracks. Device ID: {device_id} ---")
    sys.stdout.flush()
    success = spotify_service.queue_tracks(sp, track_uris, device_id)
    if success:
        print("--- /api/queue: Tracks queued successfully. ---")
        sys.stdout.flush()
        return jsonify({"message": "Tracks added to queue."}), 200
    else:
        print("--- /api/queue: Failed to queue tracks. ---")
        sys.stdout.flush()
        return jsonify({"error": "Failed to add tracks to queue."}), 500

@app.route('/api/devices', methods=['GET'])
def get_devices_route():
    print("--- /api/devices route hit ---")
    sys.stdout.flush()
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        print("--- /api/devices: User not authenticated. ---")
        sys.stdout.flush()
        return jsonify({"error": "User not authenticated or token expired. Please login."}), 401
    
    devices = spotify_service.get_available_devices(sp)
    print(f"--- /api/devices: Found {len(devices)} devices. ---")
    sys.stdout.flush()
    return jsonify({"devices": devices}), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    try:
        # Check database connection - get a fresh connection for serverless
        db_status = "unknown"
        try:
            conn = get_db_connection()
            if conn:
                # With pg8000, the connection itself is the cursor
                conn.run("SELECT 1")
                close_db_connection(conn)
                db_status = "connected"
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            db_status = f"error: {str(e)}"
            
        return jsonify({
            "status": "healthy", 
            "database": db_status,
            "serverless_mode": "enabled"
        }), 200 if db_status == "connected" else 207  # 207 = Multi-Status
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy", 
            "error": str(e),
            "serverless_mode": "enabled"
        }), 500

@app.after_request
def add_cors_headers(response):
    frontend_url = os.getenv("FRONTEND_URL") or "https://spotify-mood-player.vercel.app"
    response.headers['Access-Control-Allow-Origin'] = frontend_url
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,cache-control,Pragma'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return response

if __name__ == '__main__':
    # For local development, app.run will use the port from SERVER_NAME or default
    if not IS_PRODUCTION:
        local_run_port_str = app.config['SERVER_NAME'].split(':')[-1]
        local_run_port = int(local_run_port_str) if local_run_port_str.isdigit() else 5001
        app.run(debug=True, host='0.0.0.0', port=local_run_port)
    # In production, Gunicorn uses the PORT environment variable set by Render.
    # The SERVER_NAME config is for Flask's URL generation and cookie domain setting.

@app.route('/api/auth', methods=['POST'])
def process_auth():
    print("--- /api/auth route hit ---")
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        print("--- No authorization code provided ---")
        return jsonify({"error": "No authorization code provided"}), 400

    try:
        auth_manager = spotify_service.create_spotify_oauth()
        # Exchange the code for token info
        token_info = auth_manager.get_access_token(code)
        
        if not token_info:
            print("--- Failed to get token info ---")
            return jsonify({"error": "Failed to get token info"}), 400

        # Store the token info in session
        session['spotify_token_info'] = token_info
        session.modified = True
        print("--- Token stored in session successfully ---")
        
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"--- Error processing auth code: {str(e)} ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500