# this file analyzes the mood of songs and then categorizes them
import pandas as pd
# from textblob import TextBlob # Example for sentiment analysis
# import spotipy # If you need to fetch song details

# This file is conceptual and outlines how you might approach
# a more in-depth sentiment analysis and categorization if desired.
# For the real-time mood player, app.py uses Spotify's audio features.

def fetch_user_library_songs(sp_client):
    """
    Fetches all songs from a user's Spotify library (saved tracks).
    This can be a lot of songs and API calls.
    Args:
        sp_client: Authenticated Spotipy client.
    Returns:
        A list of track objects or details.
    """
    print("Fetching user library songs... This might take a while.")
    all_tracks = []
    offset = 0
    limit = 50
    while True:
        results = sp_client.current_user_saved_tracks(limit=limit, offset=offset)
        if not results or not results['items']:
            break
        for item in results['items']:
            if item['track']:
                all_tracks.append(item['track'])
        offset += limit
        if len(results['items']) < limit:
            break # Reached the end
    print(f"Fetched {len(all_tracks)} songs from user library.")
    return all_tracks

def analyze_song_mood(track_info):
    """
    Analyzes the mood of a single song.
    This is a placeholder for your sentiment analysis logic.
    You could use:
    1. Spotify's audio features (valence, energy, danceability, tempo) - Recommended
    2. NLP on track titles (less reliable for mood)
    3. NLP on lyrics (requires fetching lyrics from a third-party API, which is complex)
    """
    # Example using Spotify's audio features (if available in track_info or fetched separately)
    valence = track_info.get('valence', 0.5) # Assuming audio features are pre-fetched
    energy = track_info.get('energy', 0.5)

    if valence > 0.7 and energy > 0.6:
        return "very_happy_energetic"
    elif valence > 0.5 and energy > 0.5:
        return "happy"
    elif valence < 0.3 and energy < 0.4:
        return "sad_calm"
    elif energy > 0.7:
        return "energetic"
    elif energy < 0.3:
        return "calm"
    else:
        return "neutral"

def create_mood_categorized_dataframe(tracks_data):
    """
    Creates a Pandas DataFrame with songs categorized by mood.
    Args:
        tracks_data: A list of dictionaries, where each dict contains track info
                     (e.g., id, name, artist, and features needed for mood analysis).
    Returns:
        A Pandas DataFrame.
    """
    if not tracks_data:
        return pd.DataFrame()

    analyzed_songs = []
    for track in tracks_data:
        # Assuming 'track' dict contains 'id', 'name', 'artists', and audio features
        # If audio features are not present, you'd need to fetch them:
        # features = sp_client.audio_features(tracks=[track['id']])[0]
        # track_full_info = {**track, **features} if features else track

        mood = analyze_song_mood(track) # track should have audio features here
        analyzed_songs.append({
            'id': track.get('id'),
            'name': track.get('name'),
            'artists': ", ".join([artist['name'] for artist in track.get('artists', [])]),
            'album': track.get('album', {}).get('name'),
            'spotify_url': track.get('external_urls', {}).get('spotify'),
            'mood_category': mood,
            'valence': track.get('valence'), # Store actual features too
            'energy': track.get('energy'),
            'danceability': track.get('danceability'),
            'tempo': track.get('tempo'),
        })

    df = pd.DataFrame(analyzed_songs)
    return df

# --- Example Usage (Illustrative - not directly used by the real-time app.py) ---
if __name__ == "__main__":
    # This part would require user authentication first to get an sp_client
    # For example, you might run this as a script after a user logs in
    # and you have their Spotipy client object.

    # 0. Authenticate (this is complex for a standalone script, usually part of web flow)
    # print("This script is illustrative. Authentication needs to be handled.")
    # print("Assuming you have an authenticated `sp` (Spotipy client) object...")
    # Example:
    # auth_manager = spotipy.SpotifyOAuth(client_id="YOUR_ID", client_secret="YOUR_SECRET",
    #                                     redirect_uri="YOUR_REDIRECT_URI", scope="user-library-read")
    # sp = spotipy.Spotify(auth_manager=auth_manager)
    #
    # if not auth_manager.get_cached_token():
    #     auth_url = auth_manager.get_authorize_url()
    #     print(f"Please navigate here: {auth_url}")
    #     response = input("Enter the URL you were redirected to: ")
    #     code = auth_manager.parse_response_code(response)
    #     auth_manager.get_access_token(code)
    #     sp = spotipy.Spotify(auth_manager=auth_manager)


    # 1. Fetch songs (e.g., from user's library)
    # user_songs_raw = fetch_user_library_songs(sp) # Needs authenticated sp

    # 2. Fetch audio features for these songs (Spotify API allows up to 100 IDs per call)
    # track_ids = [track['id'] for track in user_songs_raw if track and track.get('id')]
    # all_song_features_data = []
    # for i in range(0, len(track_ids), 100):
    #     batch_ids = track_ids[i:i+100]
    #     features_list = sp.audio_features(tracks=batch_ids)
    #     # Combine raw track info with features
    #     for j, raw_track_info in enumerate(user_songs_raw[i:i+len(batch_ids)]):
    #          if features_list[j]: # Ensure features were found
    #              all_song_features_data.append({**raw_track_info, **features_list[j]})


    # 3. Create DataFrame
    # mood_df = create_mood_categorized_dataframe(all_song_features_data)
    # if not mood_df.empty:
    #     print("\n--- Mood Categorized DataFrame ---")
    #     print(mood_df.head())
    #     print(f"\nValue counts for mood_category:\n{mood_df['mood_category'].value_counts()}")
        # You could save this DataFrame to a CSV, database, etc.
        # mood_df.to_csv("user_spotify_moods.csv", index=False)
        # print("\nSaved to user_spotify_moods.csv")
    # else:
    #     print("No data to process or DataFrame is empty.")
    pass
