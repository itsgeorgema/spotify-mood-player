# this file has functions that govern main logic for Spotify API interactions, fetching songs, playing songs, and authorizing user accounts
import os
import spotipy
from flask import session
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
from spotipy.cache_handler import MemoryCacheHandler

SCOPE = "user-read-private user-read-email user-library-read playlist-read-private streaming user-modify-playback-state user-read-playback-state"

def create_spotify_oauth(token_info=None):
    cache_handler = MemoryCacheHandler(token_info=token_info)
    return SpotifyOAuth(
        client_id=os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI"),
        scope=SCOPE,
        cache_handler=cache_handler,
        show_dialog=True
    )

def get_spotify_client_from_session():
    token_info = session.get('spotify_token_info', None)
    if not token_info:
        return None
    auth_manager = create_spotify_oauth(token_info)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    new_token_info = auth_manager.get_cached_token()
    if new_token_info and new_token_info != token_info:
        session['spotify_token_info'] = new_token_info
        session.modified = True
    return sp

def play_tracks(sp: spotipy.Spotify, track_uris: list, device_id: str | None = None):
    """
    Starts playback of the given tracks on the user's active or specified device.
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
        return False

def queue_tracks(sp: spotipy.Spotify, track_uris: list, device_id: str | None = None):
    """
    Adds the given tracks to the user's playback queue.
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
