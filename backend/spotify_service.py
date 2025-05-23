# this file has functions that govern main logic for Spotify API interactions, fetching songs, playing songs, and authorizing user accounts
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

SCOPE = "user-read-private user-read-email user-library-read playlist-read-private streaming user-modify-playback-state user-read-playback-state"

def create_spotify_oauth():
    """Creates a SpotifyOAuth object for authentication."""
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=SCOPE,
        show_dialog=True,
        cache_path=None #make sure to set this to None to avoid caching issues
        #DO NOT STORE CACHE because sensitive data and also because our method of storing tokens
        #is in the session cookies from Flask (more security because encrypted by FLASK_SECRET_KEY)
    )

# ...existing imports...

def get_spotify_client_from_session():
    """
    Gets a Spotipy client instance using tokens stored in the session.
    Handles token refresh if needed.
    """
    token_info = session.get('spotify_token_info', None)
    if not token_info:
        return None

    # Check if token needs refresh
    if int(token_info['expires_at']) - int(time.time()) < 60:
        try:
            auth_manager = create_spotify_oauth()
            new_token = auth_manager.refresh_access_token(token_info['refresh_token'])
            session['spotify_token_info'] = {
                'access_token': new_token['access_token'],
                'refresh_token': new_token.get('refresh_token', token_info['refresh_token']),
                'expires_at': new_token['expires_at']
            }
            session.modified = True
            access_token = new_token['access_token']
        except Exception as e:
            print(f"Token refresh failed: {e}")
            session.pop('spotify_token_info', None)
            return None
    else:
        access_token = token_info['access_token']

    return spotipy.Spotify(auth=access_token)

def get_tracks_for_mood(sp: spotipy.Spotify, mood: str, limit: int = 20):
    """
    Fetches tracks from Spotify based on mood using audio features.
    This is a simplified approach. You can make this much more sophisticated.

    Args:
        sp: Authenticated Spotipy client.
        mood: A string representing the mood (e.g., "happy", "sad", "energetic", "calm").
        limit: Number of tracks to fetch.

    Returns:
        A list of track URIs.
    """
    if not sp:
        raise ValueError("Spotify client not initialized.")

    # Define audio feature targets based on mood
    # These are examples; you'll want to fine-tune them.
    # Valence: 0.0 (sad/negative) to 1.0 (happy/positive)
    # Energy: 0.0 (calm) to 1.0 (energetic)
    # Danceability: 0.0 to 1.0
    # Tempo: in BPM

    seed_genres = [] # Optional: add seed genres like ['pop', 'dance']
    target_features = {}

    if mood == "happy":
        target_features = {"target_valence": 0.8, "target_energy": 0.7, "min_danceability": 0.6}
        seed_genres = ['pop', 'dance', 'happy']
    elif mood == "sad":
        target_features = {"target_valence": 0.2, "target_energy": 0.3, "max_danceability": 0.5}
        seed_genres = ['acoustic', 'sad', 'ambient']
    elif mood == "energetic":
        target_features = {"target_energy": 0.9, "min_tempo": 120, "min_danceability": 0.7}
        seed_genres = ['electronic', 'rock', 'workout']
    elif mood == "calm":
        target_features = {"target_valence": 0.5, "target_energy": 0.2, "max_tempo": 100}
        seed_genres = ['chill', 'ambient', 'classical']
    else: # Default or unknown mood
        target_features = {"target_valence": 0.5, "target_energy": 0.5}
        seed_genres = ['pop']


    try:
        recommendations = sp.recommendations(
            seed_genres=seed_genres if seed_genres else None,
            limit=limit,
            **target_features
        )
        track_uris = [track['uri'] for track in recommendations['tracks']]
        return track_uris
    except SpotifyException as e:
        print(f"Error fetching recommendations for mood '{mood}': {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return []


def play_tracks(sp: spotipy.Spotify, track_uris: list, device_id: str = None):
    """
    Starts playback of the given tracks on the user's active or specified device.

    Args:
        sp: Authenticated Spotipy client.
        track_uris: A list of Spotify track URIs.
        device_id: Optional. The ID of the device to play on. If None, plays on active device.
    """
    if not sp:
        raise ValueError("Spotify client not initialized.")
    if not track_uris:
        print("No track URIs provided to play.")
        return False

    try:
        sp.start_playback(device_id=device_id, uris=track_uris)
        print(f"Started playback of {len(track_uris)} tracks.")
        return True
    except SpotifyException as e:
        print(f"Error starting playback: {e}")
        # Common errors: No active device, device not found, premium required
        if "No active device found" in str(e) or "Device not found" in str(e):
            print("Hint: User needs to have an active Spotify device (e.g., Spotify app open and playing).")
        elif "Player command failed: Premium required" in str(e):
            print("Hint: Spotify Premium is required for this feature.")
        return False

def queue_tracks(sp: spotipy.Spotify, track_uris: list, device_id: str = None):
    """
    Adds the given tracks to the user's playback queue.

    Args:
        sp: Authenticated Spotipy client.
        track_uris: A list of Spotify track URIs.
        device_id: Optional. The ID of the device (though queue is usually for active device).
    """
    if not sp:
        raise ValueError("Spotify client not initialized.")
    if not track_uris:
        print("No track URIs provided to queue.")
        return False

    try:
        for track_uri in track_uris:
            sp.add_to_queue(uri=track_uri, device_id=device_id)
        print(f"Added {len(track_uris)} tracks to the queue.")
        return True
    except SpotifyException as e:
        print(f"Error adding tracks to queue: {e}")
        return False

def get_available_devices(sp: spotipy.Spotify):
    """Gets a list of the user's available Spotify devices."""
    if not sp:
        raise ValueError("Spotify client not initialized.")
    try:
        devices = sp.devices()
        return devices['devices'] if devices and 'devices' in devices else []
    except SpotifyException as e:
        print(f"Error fetching devices: {e}")
        return []
