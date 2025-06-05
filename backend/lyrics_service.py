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
from naive_bayes import NaiveBayesMoodClassifier
import time
import csv
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

# Download required NLTK data
nltk.download('vader_lexicon', quiet=True)

def load_training_data():
    """Load training data from CSV file."""
    training_data = []
    csv_path = pathlib.Path(__file__).parent / 'training_data.csv'
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Split moods string into list and strip whitespace
                moods = [mood.strip() for mood in row['moods'].split(',')]
                training_data.append((row['lyrics'], moods))
        print(f"Loaded {len(training_data)} training examples from CSV")
        return training_data
    except Exception as e:
        print(f"Error loading training data: {e}")
        # Return minimal training data as fallback
        return [
            ("I'm so happy", ["happy"]),
            ("I'm so sad", ["sad"]),
            ("I'm so energetic", ["energetic"]),
            ("I'm so calm", ["calm"]),
    ("I'm so mad", ["mad"]),
            ("I'm so romantic", ["romantic"]),
    ("I'm so focused", ["focused"]),
            ("I'm so mysterious", ["mysterious"])
] 

# Load training data from CSV
training_data = load_training_data()
naive_bayes_clf = NaiveBayesMoodClassifier()
if training_data:
    naive_bayes_clf.fit(training_data)

def create_genius_client():
    """Create a Genius client with proper SSL configuration, retries, and custom User-Agent"""
    try:
        token = os.getenv('GENIUS_ACCESS_TOKEN')
        if not token:
            print("WARNING: GENIUS_ACCESS_TOKEN is not set")
            return None
        print(f"Using Genius token: {token[:5]}...{token[-5:]}")  # Only log first/last 5 chars for security
        
        print("Creating Genius client...")
        genius = Genius(
            token,
            verbose=True,  # Enable verbose mode to see API requests
            remove_section_headers=True,
            timeout=30,  # Increased timeout
            retries=10,   # Increased retries
            sleep_time=5  # Increased sleep time between retries
        )
        print("Genius client created successfully")
        
        # Set a more realistic User-Agent
        print("Updating Genius client headers...")
        genius.session.headers.update({  # type: ignore[attr-defined]
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://genius.com',
            'Referer': 'https://genius.com/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        })
        print("Genius client headers updated")
        return genius
    except Exception as e:
        print(f"Error creating Genius client: {e}")
        import traceback; traceback.print_exc()
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

def bag_of_words_mood_boost(lyrics):
    # Define keywords for each mood with expanded song-specific vocabulary
    mood_keywords = {
        'romantic': [
            "love", "heart", "kiss", "baby", "darling", "sweet", "forever", "together", 
            "soul", "passion", "desire", "romance", "beautiful", "perfect", "dream", 
            "hold", "touch", "feel", "forever", "soulmate", "cherish", "adore", "belong"
        ],
        'mysterious': [
            "night", "dark", "shadow", "secret", "mystery", "moon", "whisper", "silence",
            "unknown", "hidden", "ghost", "haunt", "echo", "fog", "mist", "twilight",
            "dusk", "dawn", "veil", "enigma", "puzzle", "riddle", "curse", "spell"
        ],
        'mad': [
            "hate", "anger", "rage", "fight", "scream", "mad", "fury", "revenge",
            "betray", "hurt", "pain", "break", "destroy", "burn", "fire", "storm",
            "rage", "furious", "enemy", "war", "battle", "fight", "rage", "wrath"
        ],
        'sad': [
            "cry", "tears", "alone", "goodbye", "miss", "pain", "blue", "hurt",
            "broken", "empty", "lonely", "lost", "regret", "sorry", "sorrow", "grief",
            "heartache", "missing", "gone", "fade", "die", "end", "dark", "cold"
        ],
        'happy': [
            "joy", "smile", "sun", "shine", "dance", "happy", "bright", "light",
            "laugh", "fun", "play", "sing", "celebrate", "party", "cheer", "glad",
            "wonderful", "amazing", "beautiful", "perfect", "dream", "hope", "love", "life"
        ],
        'energetic': [
            "run", "move", "jump", "fire", "wild", "energy", "power", "strong",
            "fast", "quick", "speed", "rush", "pump", "beat", "rhythm", "dance",
            "party", "rock", "loud", "bass", "drums", "electric", "thunder", "storm"
        ],
        'calm': [
            "peace", "quiet", "slow", "breeze", "dream", "calm", "soft", "gentle",
            "easy", "smooth", "flow", "float", "drift", "rest", "sleep", "relax",
            "serene", "tranquil", "soothe", "hush", "whisper", "silence", "still", "cool"
        ],
        'focused': [
            "work", "focus", "drive", "goal", "win", "plan", "mind", "think",
            "learn", "grow", "build", "create", "achieve", "success", "power", "strength",
            "determine", "decide", "choose", "path", "way", "journey", "forward", "ahead"
        ]
    }
    lyrics_lower = lyrics.lower() if lyrics else ""
    mood_boost = {mood: 0 for mood in mood_keywords}
    
    # Count word occurrences with weighted scoring
    for mood, keywords in mood_keywords.items():
        for word in keywords:
            # Count occurrences and weight them based on word importance
            count = lyrics_lower.count(word)
            if count > 0:
                # Core words get higher weight
                if word in ['love', 'hate', 'happy', 'sad', 'energy', 'calm', 'focus', 'mystery']:
                    mood_boost[mood] += count * 2
                else:
                    mood_boost[mood] += count
    
    return mood_boost

def analyze_track(track, genius):
    """Analyze a single track with all its features."""
    print(f"Analyzing track: {track['name']} by {track['artist']}")
    itunes_preview_url = get_itunes_preview(track['name'], track['artist'])
    audio_features = {'tempo': 0, 'energy': 0, 'brightness': 0, 'zcr': 0, 'contrast': 0}
    wav_path = None
    y = None
    sr = None
    song = None
    lyrics = None
    sentiment = 0

    try:
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
                    raise  # Re-raise the exception to see the full error
                finally:
                    if wav_path and os.path.exists(wav_path):
                        os.remove(wav_path)
                    del wav_path
                    if y is not None:
                        del y
                    if sr is not None:
                        del sr
        else:
            print(f"No iTunes preview found for {track['name']}")

        if genius:
            try:
                print(f"Attempting to fetch lyrics for '{track['name']}' by '{track['artist']}'")
                token = os.getenv('GENIUS_ACCESS_TOKEN')
                if token:
                    print(f"Using Genius token: {token[:5]}...{token[-5:]}")
                else:
                    print("WARNING: GENIUS_ACCESS_TOKEN is not set")
                song = genius.search_song(track['name'], track['artist'])
                if song:
                    lyrics = song.lyrics
                    print(f"Successfully fetched lyrics for {track['name']}")
                    print(f"Lyrics length: {len(lyrics)} characters")
                else:
                    print(f"No lyrics found for {track['name']} - API returned no results")
            except Exception as e:
                print(f"Error fetching lyrics for '{track['name']}' by '{track['artist']}':")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                if isinstance(e, requests.exceptions.RequestException) and hasattr(e, 'response') and e.response is not None:
                    print(f"Response status code: {e.response.status_code}")
                    print(f"Response headers: {e.response.headers}")
                    print(f"Response body: {e.response.text}")
                import traceback
                print("Full error traceback:")
                print(traceback.format_exc())
            time.sleep(2)  # Rate limiting

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
            sentiment=sentiment,
            lyrics=lyrics
        )
        print(f"Moods for {track['name']}: {track['moods']}")
        return track

    except Exception as e:
        print(f"Error analyzing track {track['name']}: {e}")
        import traceback
        print("Full error traceback:")
        print(traceback.format_exc())
        raise  # Re-raise the exception to see the full error
    finally:
        # Cleanup
        if lyrics:
            del lyrics
        if song:
            del song

def analyze_user_library(sp, session=None):
    """Analyze user's library using parallel processing."""
    print("Fetching user's library...")
    print("Creating Genius client...")
    genius = create_genius_client()
    if not genius:
        print("WARNING: Failed to create Genius client - lyrics will not be fetched")
    else:
        print("Genius client created successfully")
    analyzed_tracks = []
    
    try:
        offset = 0
        limit = 5  # Reduced batch size further
        max_workers = min(4, (os.cpu_count() or 1))  # Reduced max workers further
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
                
                print(f"Processing batch of {len(batch_tracks)} tracks (offset {offset})")
                
                # Submit all tracks in the batch for parallel processing
                future_to_track = {
                    executor.submit(analyze_track, track, genius): track 
                    for track in batch_tracks
                }
                
                # Collect results as they complete
                for future in as_completed(future_to_track):
                    track = future_to_track[future]
                    try:
                        result = future.result()
                        if result:
                            analyzed_tracks.append(result)
                            print(f"Successfully analyzed track: {track['name']}")
                    except Exception as e:
                        print(f"Error processing track {track['name']}: {e}")
                        import traceback; traceback.print_exc()
                
                offset += limit
                if len(batch_tracks) < limit:
                    break
                
                # Increased delay between batches
                print("Waiting 10 seconds before next batch...")
                time.sleep(10)  # Increased from 2 to 10 seconds
        
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
        
        return analyzed_tracks, mood_uris
        
    except Exception as e:
        print(f"Error in analyze_user_library: {e}")
        import traceback; traceback.print_exc()
        return [], {}

def categorize_mood(tempo, energy, brightness, zcr, contrast, sentiment, lyrics=None):
    moods = []
    # Use Naive Bayes classifier if lyrics and model are available
    nb_moods = []
    if lyrics and training_data:
        nb_moods = naive_bayes_clf.predict(lyrics, threshold=0.15)  # Lower threshold for more multi-label
        moods.extend(nb_moods)
    # Bag-of-words boost (legacy, can be removed if NB is good)
    bow_boost = bag_of_words_mood_boost(lyrics) if lyrics else {k:0 for k in ['romantic','mysterious','mad','sad','happy','energetic','calm','focused']}
    # Audio/sentiment-based adjusters (only add if not already present)
    if (sentiment > 0.5 and brightness > 2500 and energy > 0.07 or bow_boost['happy'] > 1) and 'happy' not in moods:
        moods.append("happy")
    if (sentiment < -0.3 and brightness < 2000 and energy < 0.06 or bow_boost['sad'] > 1) and 'sad' not in moods:
        moods.append("sad")
    if (tempo > 115 and energy > 0.08 and zcr > 0.09 or bow_boost['energetic'] > 1) and 'energetic' not in moods:
        moods.append("energetic")
    if (tempo < 90 and energy < 0.05 and zcr < 0.05 and contrast < 20 or bow_boost['calm'] > 1) and 'calm' not in moods:
        moods.append("calm")
    if (sentiment < -0.2 and energy > 0.07 and zcr > 0.08 or bow_boost['mad'] > 1) and 'mad' not in moods:
        moods.append("mad")
    if (sentiment > 0.2 and 85 < tempo < 115 and brightness > 2200 and zcr < 0.07 or bow_boost['romantic'] > 1) and 'romantic' not in moods:
        moods.append("romantic")
    if (85 <= tempo <= 115 and 0.04 <= energy <= 0.07 and -0.2 < sentiment < 0.2 and contrast < 22 and zcr < 0.07 or bow_boost['focused'] > 1) and 'focused' not in moods:
        moods.append("focused")
    if (80 <= tempo <= 120 and brightness < 1800 and contrast > 22 and -0.4 < sentiment < 0.2 or bow_boost['mysterious'] > 1) and 'mysterious' not in moods:
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