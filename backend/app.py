import os
import sys # For flushing output
import traceback
from datetime import timedelta  
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import time
from lyrics_service import analyze_user_library, get_tracks_for_mood
import spotify_service

# Attempt to load dotenv and check its status
try:
    from dotenv import load_dotenv
    print("--- python-dotenv module found. Attempting to load .env file... ---")
    if os.path.exists('.env'):
        print("--- .env file found in backend directory. ---")
        load_success = load_dotenv()
        if load_success:
            print("--- .env file loaded successfully. ---")
        else:
            print("--- WARNING: load_dotenv() called but reported no variables loaded. Check .env content or permissions. ---")
    else:
        print("--- WARNING: .env file not found in backend directory. Relying on system environment variables for production. ---")
except ImportError:
    print("--- WARNING: python-dotenv module not found. pip install python-dotenv if you are using a .env file for local dev. ---")
    print("--- Relying on system environment variables. ---")
sys.stdout.flush()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
print(f"SECRET KEY IS THIS: {app.secret_key}")

# --- Environment-Specific Configuration ---
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production'
backend_port_local_dev = os.getenv('PORT', '5001') # Default for local, Render sets its own PORT env var for Gunicorn

if IS_PRODUCTION:
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
    print(f"--- Flask SERVER_NAME (Production): {app.config['SERVER_NAME']} ---")
else: # Local development
    app.config['SERVER_NAME'] = f"127.0.0.1:{backend_port_local_dev}"
    app.config.update(
        SESSION_COOKIE_SECURE=False,  # Set to True in production
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_PATH='/',
        PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
        SESSION_REFRESH_EACH_REQUEST=True
    )
    print(f"--- Flask SERVER_NAME (Development): {app.config['SERVER_NAME']} ---")

print(f"--- Flask Session Cookie SAMESITE: {app.config['SESSION_COOKIE_SAMESITE']} ---")
print(f"--- Flask Session Cookie SECURE: {app.config['SESSION_COOKIE_SECURE']} ---")
print(f"--- Flask Session Cookie HTTPONLY: {app.config['SESSION_COOKIE_HTTPONLY']} ---")
print(f"--- Flask Session Cookie PATH: {app.config['SESSION_COOKIE_PATH']} ---")
if 'SESSION_COOKIE_DOMAIN' in app.config: # Print domain only if explicitly set
    print(f"--- Flask Session Cookie DOMAIN: {app.config.get('SESSION_COOKIE_DOMAIN')} ---")
sys.stdout.flush()

# CORS CONFIG
frontend_url_from_env = os.getenv("FRONTEND_URL")

if not frontend_url_from_env:
    frontend_url_from_env = "http://127.0.0.1:5173"
allowed_origins = [frontend_url_from_env]

CORS(app, 
     resources={r"/api/*": {
         "origins": [frontend_url_from_env],
         "supports_credentials": True,
         "expose_headers": ["Set-Cookie", "Authorization"],
         "allow_headers": ["Content-Type", "Authorization"],
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
        print(f"--- Generated Spotify auth URL with client_id: {os.getenv('SPOTIPY_CLIENT_ID')} ---")
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

        print(f"--- CALLBACK DEBUG: Received code: {code} ---")
        sys.stdout.flush()
        
        if not code:
            print("--- /api/callback: No code provided ---")
            return redirect(f"{frontend_url_from_env}/?error=no_code")

        # Exchange authorization code for tokens
        token_info = auth_manager.get_access_token(code)

        print(f"--- CALLBACK DEBUG: Token info after get_access_token: {token_info} ---")
        sys.stdout.flush()
        
        # Store tokens in session with explicit session configuration
        session.permanent = True  # Make the session permanent
        session['spotify_token_info'] = token_info
        session.modified = True
        
        print("--- Token stored in session successfully ---")
        print(f"--- Token info: {token_info} ---")
        print(f"--- Full session content: {dict(session)} ---")
        sys.stdout.flush()
        
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
    print(f"--- /api/check_auth: Request cookies: {request.cookies} ---")
    print(f"--- /api/check_auth: Current session content: {dict(session)} ---")
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
    session.pop('spotify_token_info', None)
    session.modified = True 
    print("--- User logged out, token removed from session. ---")
    sys.stdout.flush()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route('/api/sentiment_analysis', methods=['POST'])
def sentiment_analysis_route():
    print("--- /api/sentiment_analysis route hit ---")
    sys.stdout.flush()
    
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        print("--- /api/sentiment_analysis: User not authenticated. ---")
        sys.stdout.flush()
        return jsonify({"error": "User not authenticated or token expired. Please login."}), 401

    # Check if we already have mood data
    existing_mood_uris = session.get('mood_uris')
    if existing_mood_uris and any(existing_mood_uris.values()):
        print("--- Using existing mood analysis ---")
        return jsonify({
            "message": "Using existing analysis",
            "available_moods": list(existing_mood_uris.keys())
        }), 200

    try:
        # Analyze user's library and get mood->uris dict
        mood_uris = analyze_user_library(sp)
        if not mood_uris:
            print("--- No tracks analyzed ---")
            return jsonify({"error": "No tracks found to analyze"}), 404
        session['mood_uris'] = mood_uris
        session.modified = True
        print(f"--- Analyzed and stored moods: {list(mood_uris.keys())} ---")
        sys.stdout.flush()
        return jsonify({
            "message": "Library analyzed successfully",
            "available_moods": list(mood_uris.keys())
        }), 200
    except Exception as e:
        print(f"--- Error in sentiment analysis: {e} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Failed to analyze library"}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze_library_route():
    """route to manually trigger library analysis"""
    print("--- /api/analyze route hit ---")
    sys.stdout.flush()
    
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        print("--- /api/analyze: User not authenticated ---")
        return jsonify({"error": "Not authenticated"}), 401

    try:
        mood_uris = analyze_user_library(sp)
        if not mood_uris:
            return jsonify({"error": "No tracks found"}), 404

        session['mood_uris'] = mood_uris
        session['last_analysis'] = time.time()
        session.modified = True

        # Count total tracks and moods
        total_tracks = sum(len(uris) for uris in mood_uris.values())
        moods = list(mood_uris.keys())

        return jsonify({
            "message": "Analysis complete",
            "tracks_analyzed": total_tracks,
            "moods": moods
        }), 200
    except Exception as e:
        print(f"Error in analyze route: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/mood-tracks', methods=['GET'])
def get_mood_tracks_route():
    print("--- /api/mood-tracks route hit ---")
    sys.stdout.flush()
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    mood = request.args.get('mood')
    if not mood:
        return jsonify({"error": "No mood specified"}), 400
    mood_uris = session.get('mood_uris')
    if not mood_uris:
        print("--- No analyzed tracks in session. Please analyze your library first. ---")
        return jsonify({"error": "No analyzed tracks in session. Please analyze your library first."}), 400
    track_uris = get_tracks_for_mood(mood_uris, mood)
    if not track_uris:
        print(f"--- No tracks found for mood: {mood} ---")
        return jsonify({"track_uris": []}), 200  # Return empty array instead of error
    print(f"--- Found {len(track_uris)} tracks for mood: {mood} ---")
    return jsonify({"track_uris": track_uris}), 200

@app.route('/api/play', methods=['POST'])
def play_tracks_route():
    print("--- /api/play route hit ---")
    sys.stdout.flush()
    sp = spotify_service.get_spotify_client_from_session()
    if not sp:
        return jsonify({"error": "Not authenticated"}), 401
    data = request.json or {}
    track_uris = data.get('track_uris')
    device_id = data.get('device_id')
    if not track_uris:
        return jsonify({"error": "No tracks provided"}), 400
    if not device_id:
        return jsonify({"error": "No device selected. Please select a playback device in Spotify and try again."}), 400
    try:
        print(f"--- Attempting to play {len(track_uris)} tracks on device {device_id} ---")
        sp.start_playback(device_id=device_id, uris=track_uris)
        return jsonify({"message": "Playback started"}), 200
    except Exception as e:
        print(f"--- Error starting playback: {str(e)} ---")
        return jsonify({"error": "Failed to start playback. Make sure your Spotify app is open and a device is active."}), 500
        
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
    print("--- /api/health route hit ---")
    sys.stdout.flush()
    return jsonify({"status": "healthy", "message": "Backend is running!"}), 200

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
        print(f"--- Session content: {dict(session)} ---")
        
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"--- Error processing auth code: {str(e)} ---")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500