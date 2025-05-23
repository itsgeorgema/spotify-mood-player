import os
import sys # For flushing output
import traceback
from datetime import timedelta  
from flask import Flask, request, jsonify, redirect, session
from flask_cors import CORS
import spotipy

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

# Assuming spotify_service.py is in the same backend directory
import spotify_service

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


# --- Helper to get Spotipy client from session ---
# (get_spotify_client_from_session function remains the same as in the previous "Explicit Cookie Domain" version)
def get_spotify_client_from_session():
    token_info = session.get('spotify_token_info', None)
    if not token_info:
        print("--- get_spotify_client_from_session: No token_info in session. ---")
        sys.stdout.flush()
        return None
    try:
        auth_manager = spotify_service.create_spotify_oauth() 
    except ValueError as ve:
        print(f"--- ERROR in get_spotify_client_from_session when creating auth_manager: {ve} ---")
        sys.stdout.flush()
        return None 
    if auth_manager.is_token_expired(token_info):
        print("--- Spotify token is expired. Attempting to refresh... ---")
        sys.stdout.flush()
        try:
            token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
            session['spotify_token_info'] = token_info
            session.modified = True 
            print("--- Spotify token refreshed successfully. ---")
            sys.stdout.flush()
        except Exception as e:
            print(f"--- Error refreshing Spotify token: {e}. User may need to re-login. ---")
            traceback.print_exc()
            sys.stdout.flush()
            session.pop('spotify_token_info', None) 
            return None
    if not token_info:
        return None
    sp_client = spotipy.Spotify(auth=token_info['access_token'])
    print(f"--- get_spotify_client_from_session: Spotipy client created: {sp_client} (Type: {type(sp_client)}) ---")
    return sp_client

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
        
        if not code:
            print("--- /api/callback: No code provided ---")
            return redirect(f"{frontend_url_from_env}/?error=no_code")

        # Exchange authorization code for tokens
        token_info = auth_manager.get_access_token(code)
        
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

    sp_client = get_spotify_client_from_session()
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
    ##THIS IS A PLACE HOLDER FOR ACTUALLY GETTING THE TRACKS. UTILIZE FUNCTIONS FROM spotify_service.py
    #TO FETCH THE TRACKS FROM USER LIBRARY, FOR WHICH YOU WOULD THEN USE FOR SENTIMENT ANALYSIS
    data = request.get_json()
    if not data or 'tracks' not in data:
        print("--- /api/sentiment_analysis: No tracks provided. ---")
        sys.stdout.flush()
        return jsonify({"error": "No tracks provided for sentiment analysis."}), 400
    # 2. Fetch audio features for these songs (Spotify API allows up to 100 IDs per call)
        #    This logic would likely be in sentiment_analysis.py or a helper there.
        #    For simplicity, let's assume a function that handles this.
        #    Example: all_song_features_data = sentiment_analysis.fetch_features_for_tracks(sp, user_songs_raw)

    tracks = data['tracks']
    # Perform sentiment analysis on the tracks
    # THIS IS A PLACE HOLDER FOR THE ACTUAL SENTIMENT ANALYSIS LOGIC
    print(f"--- /api/sentiment_analysis: Analyzing sentiment for {len(tracks)} tracks. ---")
    sys.stdout.flush()
    # Simulate sentiment analysis results
    # USE PANDAS TO CREATE A DATAFRAME WITH SENTIMENTS AND TRACK URIS
    # PUT THE ANALYZED RESULTS INTO A CSV FILE OR JSON SERIALIZABLE FORMAT
    # WITH THE TRACKS AND THEIR MOOD TO ACCESS LATER
    # THEN, handleMoodSelect in App.tsx will read CSV FILE and use results to play the moods
    analysis_results = [{"track": track, "sentiment": "positive"} for track in tracks]
    return jsonify({"analysis": analysis_results}), 200

@app.route('/api/mood-tracks', methods=['GET'])
def get_mood_tracks_route():
    print("--- /api/mood-tracks route hit ---")
    sys.stdout.flush()
    mood = request.args.get('mood')
    if not mood:
        print("--- /api/mood-tracks: Mood parameter missing. ---")
        sys.stdout.flush()
        return jsonify({"error": "Mood parameter is required"}), 400

    sp = get_spotify_client_from_session()
    if not sp:
        print("--- /api/mood-tracks: User not authenticated. ---")
        sys.stdout.flush()
        return jsonify({"error": "User not authenticated or token expired. Please login."}), 401

    try:
        print(f"--- /api/mood-tracks: Fetching tracks for mood: {mood} ---")
        sys.stdout.flush()
        track_uris = spotify_service.get_tracks_for_mood(sp, mood)
        if track_uris:
            print(f"--- /api/mood-tracks: Found {len(track_uris)} tracks. ---")
            sys.stdout.flush()
            return jsonify({"track_uris": track_uris}), 200
        else:
            print("--- /api/mood-tracks: No tracks found or error fetching. ---")
            sys.stdout.flush()
            return jsonify({"message": "No tracks found for this mood or error fetching."}), 404
    except Exception as e:
        print(f"--- Error in /api/mood-tracks: {e} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Failed to get tracks for mood.", "details": str(e)}), 500

@app.route('/api/play', methods=['POST'])
def play_tracks_route():
    print("--- /api/play route hit ---")
    sys.stdout.flush()
    data = request.get_json()
    track_uris = data.get('track_uris')
    device_id = data.get('device_id')

    if not track_uris:
        print("--- /api/play: track_uris are required. ---")
        sys.stdout.flush()
        return jsonify({"error": "track_uris are required"}), 400

    sp = get_spotify_client_from_session()
    if not sp:
        print("--- /api/play: User not authenticated. ---")
        sys.stdout.flush()
        return jsonify({"error": "User not authenticated or token expired. Please login."}), 401

    print(f"--- /api/play: Attempting to play {len(track_uris)} tracks. Device ID: {device_id} ---")
    sys.stdout.flush()
    success = spotify_service.play_tracks(sp, track_uris, device_id)
    if success:
        print("--- /api/play: Playback started successfully. ---")
        sys.stdout.flush()
        return jsonify({"message": "Playback started."}), 200
    else:
        print("--- /api/play: Failed to start playback. ---")
        sys.stdout.flush()
        return jsonify({"error": "Failed to start playback. Ensure Spotify is active and you have Premium if required."}), 500

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

    sp = get_spotify_client_from_session()
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
    sp = get_spotify_client_from_session()
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