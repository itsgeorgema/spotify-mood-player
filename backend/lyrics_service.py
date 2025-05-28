import os
import nltk
from lyricsgenius import Genius
import random
import requests
import librosa
import numpy as np
import tempfile
from urllib.parse import quote
from pydub import AudioSegment
from nltk.sentiment import SentimentIntensityAnalyzer

# Download required NLTK data
nltk.download('vader_lexicon', quiet=True)

def create_genius_client():
    """Create a Genius client with proper SSL configuration and retries"""
    try:
        genius = Genius(
            os.getenv('GENIUS_ACCESS_TOKEN'),
            verbose=False,
            remove_section_headers=True,
            timeout=15,
            retries=3
        )
        return genius
    except Exception as e:
        print(f"Error creating Genius client: {e}")
        return None

def download_and_convert_preview(preview_url):
    """Download m4a preview and convert to wav for librosa analysis. Returns wav path or None."""
    m4a_path = None
    try:
        # Download m4a
        m4a_fd, m4a_path = tempfile.mkstemp(suffix='.m4a')
        with os.fdopen(m4a_fd, 'wb') as f:
            r = requests.get(preview_url, stream=True)
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        # Convert to wav
        wav_fd, wav_path = tempfile.mkstemp(suffix='.wav')
        os.close(wav_fd)
        audio = AudioSegment.from_file(m4a_path, format="m4a")
        audio.export(wav_path, format="wav")
        os.remove(m4a_path)
        return wav_path
    except Exception as e:
        print(f"Error downloading/converting preview: {e}")
        try:
            if m4a_path is not None and os.path.exists(m4a_path):
                os.remove(m4a_path)
        except:
            pass
        return None

def analyze_lyrics_sentiment(lyrics):
    sia = SentimentIntensityAnalyzer()
    sentiment = sia.polarity_scores(str(lyrics))
    return sentiment['compound']

def get_itunes_preview(track_name, artist_name):
    """Search iTunes for a track and return the 30s preview URL if available."""
    query = f'{track_name} {artist_name}'
    url = f'https://itunes.apple.com/search?term={quote(query)}&entity=song&limit=1'
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data['resultCount'] > 0:
                return data['results'][0].get('previewUrl')  # 30s MP3 URL
    except Exception as e:
        print(f"Error fetching iTunes preview: {e}")
    return None

def analyze_user_library(sp, session=None):
    """Analyze user's library using iTunes previews (converted to wav) and Genius lyrics. Store result in session if provided."""
    print("Fetching user's library...")
    tracks = []
    genius = create_genius_client()
    try:
        offset = 0
        limit = 20
        while True:
            results = sp.current_user_saved_tracks(limit=limit, offset=offset)
            if not results['items']:
                break
            for item in results['items']:
                track = item['track']
                if track:
                    tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artist': track['artists'][0]['name'],
                        'uri': track['uri']
                    })
            offset += limit
            if len(results['items']) < limit:
                break
        print(f"Fetched {len(tracks)} tracks from library")
        analyzed_tracks = []
        for track in tracks:
            # Always try iTunes for preview
            itunes_preview_url = get_itunes_preview(track['name'], track['artist'])
            if itunes_preview_url:
                wav_path = download_and_convert_preview(itunes_preview_url)
                audio_features = {'tempo': 0, 'energy': 0}
                if wav_path:
                    try:
                        y, sr = librosa.load(wav_path, sr=None)
                        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                        energy = float(np.mean(librosa.feature.rms(y=y)))
                        audio_features = {'tempo': tempo, 'energy': energy}
                    except Exception as e:
                        print(f"Error analyzing audio features: {e}")
                    finally:
                        if os.path.exists(wav_path):
                            os.remove(wav_path)
            else:
                audio_features = {'tempo': 0, 'energy': 0}
            lyrics = None
            sentiment = 0
            if genius:
                try:
                    song = genius.search_song(track['name'], track['artist'])
                    lyrics = song.lyrics if song else None
                except Exception as e:
                    print(f"Error fetching lyrics: {e}")
            if lyrics:
                sentiment = analyze_lyrics_sentiment(lyrics)
            track.update(audio_features)
            track['sentiment'] = sentiment
            track['mood'] = categorize_mood(audio_features['tempo'], audio_features['energy'], sentiment)
            analyzed_tracks.append(track)
        # Build mood->uris dict, limit to 100 per mood
        mood_uris = {}
        for track in analyzed_tracks:
            mood = track['mood']
            uri = track['uri']
            mood_uris.setdefault(mood, []).append(uri)
        for mood in mood_uris:
            if len(mood_uris[mood]) > 100:
                mood_uris[mood] = random.sample(mood_uris[mood], 100)
        print("Mood URI dict:", {k: len(v) for k, v in mood_uris.items()})
        # Store in session if provided
        if session is not None:
            session['mood_uris'] = mood_uris
            session.modified = True
        return mood_uris
    except Exception as e:
        print(f"Error in analyze_user_library: {e}")
        import traceback; traceback.print_exc()
        return {}  # Return empty dict

def categorize_mood(tempo, energy, sentiment):
    """
    Weighted mood categorization using both audio features and lyrics sentiment.
    - tempo: Beats per minute
    - energy: Intensity and activity (0.0 to 1.0)
    - sentiment: Sentiment score (-1.0 to 1.0)
    """
    # Weighted score: 60% lyrics sentiment, 40% audio features
    mood_score = 0.6 * sentiment + 0.2 * (energy * 2 - 1) + 0.2 * ((tempo - 90) / 60)
    # Clamp mood_score to [-1, 1]
    mood_score = max(-1, min(1, mood_score))
    # Mood logic
    if mood_score > 0.5:
        return "happy"
    if mood_score < -0.5:
        return "sad"
    if energy > 0.08 and tempo > 120:
        return "energetic"
    if energy < 0.05 and tempo < 90 and sentiment > -0.2:
        return "calm"
    if sentiment < -0.3 and energy > 0.06:
        return "mad"
    if sentiment > 0.3 and tempo < 110 and energy < 0.06:
        return "romantic"
    if 90 <= tempo <= 110 and 0.04 <= energy <= 0.07 and -0.2 < sentiment < 0.2:
        return "focused"
    if 90 <= tempo <= 110 and energy < 0.04 and -0.3 < sentiment < 0.1:
        return "mysterious"
    if tempo > 120:
        return "energetic"
    if tempo < 90:
        return "calm"
    if sentiment > 0.1:
        return "happy"
    if sentiment < -0.1:
        return "sad"
    return "happy"

def get_tracks_for_mood(mood_uris, mood, limit=20):
    """Get up to 'limit' URIs for a mood from the session dict."""
    if not mood_uris:
        return []
    uris = mood_uris.get(mood.lower(), [])
    if not uris:
        return []
    return random.sample(uris, min(len(uris), limit))