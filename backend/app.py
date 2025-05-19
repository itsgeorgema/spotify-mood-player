# backend/app.py
print("--- Starting backend/app.py ---") # Canary print

import os
import sys # For flushing output
import traceback
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
try:
    import spotify_service
    print("--- spotify_service.py imported successfully. ---")
except ImportError as e:
    print(f"--- CRITICAL ERROR: Failed to import spotify_service.py: {e} ---")
    print("--- Please ensure spotify_service.py is in the backend directory and has no syntax errors. ---")
    sys.stdout.flush()
    exit() 
sys.stdout.flush()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_dev_secret_key_MUST_BE_SET_IN_ENV")
if app.secret_key == "fallback_dev_secret_key_MUST_BE_SET_IN_ENV":
    print("--- CRITICAL WARNING: Using a fallback FLASK_SECRET_KEY. This is insecure. Set a proper FLASK_SECRET_KEY in your environment. ---")

# --- Environment-Specific Configuration ---
IS_PRODUCTION = os.getenv('FLASK_ENV') == 'production'
backend_port_local_dev = os.getenv('PORT', '5001') # Default for local, Render sets its own PORT env var for Gunicorn

if IS_PRODUCTION:
    # For Render, RENDER_EXTERNAL_HOSTNAME is automatically set and includes the domain.
    # We don't need to include the port here for SERVER_NAME as Render handles port mapping.
    app.config['SERVER_NAME'] = os.getenv('RENDER_EXTERNAL_HOSTNAME')
    if not app.config['SERVER_NAME']:
        print("--- WARNING: RENDER_EXTERNAL_HOSTNAME not found. Cookie domain might be incorrect. Consider setting a BACKEND_HOSTNAME env var. ---")
        # Fallback for safety, though RENDER_EXTERNAL_HOSTNAME should exist on Render
        app.config['SERVER_NAME'] = "spotify-mood-player-api.onrender.com" # Replace if your Render service name is different
    
    app.config.update(
        SESSION_COOKIE_SECURE=True,    # Cookies only sent over HTTPS
        SESSION_COOKIE_SAMESITE="Lax", # "Lax" is a good default. If issues persist, "None" could be tried (requires Secure=True).
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_PATH='/'
        # SESSION_COOKIE_DOMAIN is usually best left for Flask to derive from SERVER_NAME in this cross-origin setup,
        # or set it to your backend domain if SERVER_NAME isn't working as expected.
        # e.g., SESSION_COOKIE_DOMAIN = app.config['SERVER_NAME']
    )
    print(f"--- Flask SERVER_NAME (Production): {app.config['SERVER_NAME']} ---")
else: # Local development
    app.config['SERVER_NAME'] = f"127.0.0.1:{backend_port_local_dev}"
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_PATH='/',
        SESSION_COOKIE_DOMAIN="127.0.0.1" # Explicit for 127.0.0.1 local dev
    )
    print(f"--- Flask SERVER_NAME (Development): {app.config['SERVER_NAME']} ---")

print(f"--- Flask Session Cookie SAMESITE: {app.config['SESSION_COOKIE_SAMESITE']} ---")
print(f"--- Flask Session Cookie SECURE: {app.config['SESSION_COOKIE_SECURE']} ---")
print(f"--- Flask Session Cookie HTTPONLY: {app.config['SESSION_COOKIE_HTTPONLY']} ---")
print(f"--- Flask Session Cookie PATH: {app.config['SESSION_COOKIE_PATH']} ---")
if 'SESSION_COOKIE_DOMAIN' in app.config: # Print domain only if explicitly set
    print(f"--- Flask Session Cookie DOMAIN: {app.config.get('SESSION_COOKIE_DOMAIN')} ---")
sys.stdout.flush()

# --- CORS Configuration ---
frontend_url_from_env = os.getenv("FRONTEND_URL")
if not frontend_url_from_env:
    frontend_url_from_env = "http://localhost:5173" # Default for local if not set
    print(f"--- WARNING: FRONTEND_URL not set in environment, defaulting to {frontend_url_from_env} for CORS. ---")
print(f"--- CORS: Allowing frontend URL: {frontend_url_from_env} ---")
allowed_origins = [frontend_url_from_env]
# If your Vercel frontend URL is different from what FRONTEND_URL is set to in Render, add it.
# Example: if FRONTEND_URL in Render is set to your Vercel custom domain, this might not be needed.
# if IS_PRODUCTION and frontend_url_from_env != "https://spotify-mood-player.vercel.app": # Your actual Vercel URL
#     allowed_origins.append("https://spotify-mood-player.vercel.app")


CORS(app, resources={r"/api/*": {"origins": allowed_origins}}, supports_credentials=True)


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
    return spotipy.Spotify(auth=token_info['access_token'])

# --- API Routes ---
# (All API routes: /api/login, /api/callback, /api/check_auth, /api/logout, 
#  /api/mood-tracks, /api/play, /api/queue, /api/devices, /api/health 
#  remain the same as in the previous "Explicit Cookie Domain" version)
@app.route('/api/login', methods=['GET'])
def spotify_login():
    print("--- /api/login route hit ---")
    sys.stdout.flush()
    try:
        auth_manager = spotify_service.create_spotify_oauth()
        auth_url = auth_manager.get_authorize_url()
        print(f"--- Redirecting to Spotify auth URL: {auth_url[:70]}... ---") 
        sys.stdout.flush()
        return redirect(auth_url)
    except ValueError as ve:
        print(f"--- CONFIGURATION ERROR in /api/login: {ve} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Server configuration error for Spotify login.", "details": str(ve)}), 500
    except Exception as e:
        print(f"--- UNEXPECTED ERROR in /api/login: {e} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "An unexpected error occurred during login.", "details": str(e)}), 500

@app.route('/api/callback', methods=['GET'])
def spotify_callback():
    print("--- /api/callback route hit ---")
    sys.stdout.flush()
    try:
        auth_manager = spotify_service.create_spotify_oauth()
    except ValueError as ve: 
        print(f"--- CONFIGURATION ERROR in /api/callback when creating auth_manager: {ve} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Server configuration error during Spotify callback.", "details": str(ve)}), 500
        
    code = request.args.get('code')
    if not code:
        print("--- /api/callback: Authorization code not found. ---")
        sys.stdout.flush()
        return jsonify({"error": "Authorization code not found in callback."}), 400

    try:
        token_info = auth_manager.get_access_token(code)
        session['spotify_token_info'] = token_info 
        session.modified = True 
        print("--- Successfully obtained Spotify token from callback. Session 'spotify_token_info' SET and marked as modified. ---")
        print(f"--- /api/callback: Session content immediately after set: {dict(session)} ---") 
        sys.stdout.flush()
        # Use the frontend_url_from_env for the redirect
        print(f"--- Redirecting to frontend: {frontend_url_from_env}/?login_success=true ---")
        sys.stdout.flush()
        return redirect(f"{frontend_url_from_env}/?login_success=true")
    except Exception as e:
        print(f"--- Error getting token from Spotify in /api/callback: {e} ---")
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": "Failed to get token from Spotify.", "details": str(e)}), 500

@app.route('/api/check_auth', methods=['GET'])
def check_auth_status():
    print("--- /api/check_auth route hit ---")
    print(f"--- /api/check_auth: Current session content: {dict(session)} ---")
    sys.stdout.flush()
    sp_client = get_spotify_client_from_session() 
    if sp_client:
        print("--- /api/check_auth: User is authenticated. ---")
        sys.stdout.flush()
        return jsonify({"isAuthenticated": True}), 200
    else:
        print("--- /api/check_auth: User is NOT authenticated (get_spotify_client_from_session returned None). ---")
        sys.stdout.flush()
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
    print("--- Starting Flask development server... ---")
    print(f"--- FLASK_ENV: {os.getenv('FLASK_ENV')} ---")
    # For local development, app.run will use the port from SERVER_NAME or default
    if not IS_PRODUCTION:
        local_run_port_str = app.config['SERVER_NAME'].split(':')[-1]
        local_run_port = int(local_run_port_str) if local_run_port_str.isdigit() else 5001
        print(f"--- Attempting to run local dev server on host 0.0.0.0, port {local_run_port} ---")
        sys.stdout.flush()
        app.run(debug=True, host='0.0.0.0', port=local_run_port)
    # In production, Gunicorn uses the PORT environment variable set by Render.
    # The SERVER_NAME config is for Flask's URL generation and cookie domain setting.
