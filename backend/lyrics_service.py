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
        limit = 10  # Reduce batch size for lower memory usage
        analyzed_tracks = []
        while True:
            results = sp.current_user_saved_tracks(limit=limit, offset=offset)
            if not results['items']:
                break
            batch_tracks = []
            for item in results['items']:
                track = item['track']
                if track:
                    batch_tracks.append({
                        'id': track['id'],
                        'name': track['name'],
                        'artist': track['artists'][0]['name'],
                        'uri': track['uri']
                    })
            print(f"Fetched {len(batch_tracks)} tracks in batch (offset {offset})")
            # Analyze each track in the batch and release memory after each
            for track in batch_tracks:
                print(f"Analyzing track: {track['name']} by {track['artist']}")
                itunes_preview_url = get_itunes_preview(track['name'], track['artist'])
                audio_features = {'tempo': 0, 'energy': 0, 'brightness': 0, 'zcr': 0, 'contrast': 0}
                wav_path = None
                y = None
                sr = None
                song = None
                if itunes_preview_url:
                    print(f"Found iTunes preview for {track['name']}: {itunes_preview_url}")
                    wav_path = download_and_convert_preview(itunes_preview_url)
                    if wav_path:
                        try:
                            y, sr = librosa.load(wav_path, sr=None)
                            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
                            energy = float(np.mean(librosa.feature.rms(y=y)))
                            brightness = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
                            zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
                            contrast = float(np.mean(librosa.feature.spectral_contrast(y=y, sr=sr)))
                            audio_features = {
                                'tempo': tempo,
                                'energy': energy,
                                'brightness': brightness,
                                'zcr': zcr,
                                'contrast': contrast
                            }
                            print(f"Audio features for {track['name']}: {audio_features}")
                        except Exception as e:
                            print(f"Error analyzing audio features for {track['name']}: {e}")
                        finally:
                            if wav_path and os.path.exists(wav_path):
                                os.remove(wav_path)
                            # Explicitly release memory for large objects
                            del wav_path
                            if y is not None:
                                del y
                            if sr is not None:
                                del sr
                else:
                    print(f"No iTunes preview found for {track['name']}")
                lyrics = None
                sentiment = 0
                if genius:
                    try:
                        song = genius.search_song(track['name'], track['artist'])
                        lyrics = song.lyrics if song else None
                        if lyrics:
                            print(f"Fetched lyrics for {track['name']}")
                        else:
                            print(f"No lyrics found for {track['name']}")
                    except Exception as e:
                        print(f"Error fetching lyrics for {track['name']}: {e}")
                if lyrics:
                    sentiment = analyze_lyrics_sentiment(lyrics)
                    print(f"Sentiment for {track['name']}: {sentiment}")
                track.update(audio_features)
                track['sentiment'] = sentiment
                track['moods'] = categorize_mood(
                    tempo=audio_features['tempo'],
                    energy=audio_features['energy'],
                    brightness=audio_features['brightness'],
                    zcr=audio_features['zcr'],
                    contrast=audio_features['contrast'],
                    sentiment=sentiment
                )
                print(f"Moods for {track['name']}: {track['moods']}")
                analyzed_tracks.append(track)
                # Explicitly release memory for lyrics and song
                del lyrics
                if song is not None:
                    del song
            offset += limit
            if len(batch_tracks) < limit:
                break
            # Explicitly release memory for batch_tracks
            del batch_tracks
        # Build mood->uris dict, limit to 100 per mood
        mood_uris = {}
        for track in analyzed_tracks:
            for mood in track['moods']:
                mood_uris.setdefault(mood, []).append(track['uri'])
        for mood in mood_uris:
            if len(mood_uris[mood]) > 100:
                mood_uris[mood] = random.sample(mood_uris[mood], 100)
        print("Mood URI dict:", {k: len(v) for k, v in mood_uris.items()})
        # Store in session if provided
        if session is not None:
            session['mood_uris'] = mood_uris
            session.modified = True
        # Return both for compatibility
        return analyzed_tracks, mood_uris
    except Exception as e:
        print(f"Error in analyze_user_library: {e}")
        import traceback; traceback.print_exc()
        return [], {}  # Return empty dict

def categorize_mood(tempo, energy, brightness, zcr, contrast, sentiment):
    moods = []
    # Happy: very positive lyrics, bright, energetic
    if sentiment > 0.5 and brightness > 2500 and energy > 0.07:
        moods.append("happy")
    # Sad: negative lyrics, low brightness, low energy
    if sentiment < -0.3 and brightness < 2000 and energy < 0.06:
        moods.append("sad")
    # Energetic: high tempo, high energy, high zcr
    if tempo > 115 and energy > 0.08 and zcr > 0.09:
        moods.append("energetic")
    # Calm: slow, low energy, low zcr, low contrast
    if tempo < 90 and energy < 0.05 and zcr < 0.05 and contrast < 20:
        moods.append("calm")
    # Mad: negative lyrics, high energy, high zcr
    if sentiment < -0.2 and energy > 0.07 and zcr > 0.08:
        moods.append("mad")
    # Romantic: positive lyrics, moderate tempo, bright, low zcr
    if sentiment > 0.2 and 85 < tempo < 115 and brightness > 2200 and zcr < 0.07:
        moods.append("romantic")
    # Focused: neutral lyrics, moderate tempo, moderate energy, low zcr, low contrast
    if 85 <= tempo <= 115 and 0.04 <= energy <= 0.07 and -0.2 < sentiment < 0.2 and contrast < 22 and zcr < 0.07:
        moods.append("focused")
    # Mysterious: moderate tempo, low brightness, high contrast, neutral/negative sentiment
    if 80 <= tempo <= 120 and brightness < 1800 and contrast > 22 and -0.4 < sentiment < 0.2:
        moods.append("mysterious")
    # Fallbacks: assign most likely if nothing else matches
    if not moods:
        if tempo > 120:
            moods.append("energetic")
        elif tempo < 90:
            moods.append("calm")
        elif sentiment > 0.1:
            moods.append("happy")
        elif sentiment < -0.1:
            moods.append("sad")
        else:
            moods.append("happy")
    return moods

def get_tracks_for_mood(mood_uris, mood, limit=20):
    """Get up to 'limit' URIs for a mood from the session dict."""
    if not mood_uris:
        return []
    uris = mood_uris.get(mood.lower(), [])
    if not uris:
        return []
    return random.sample(uris, min(len(uris), limit))