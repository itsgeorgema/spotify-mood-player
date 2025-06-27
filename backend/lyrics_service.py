import os
from lyricsgenius import Genius
import random
import requests
import librosa
import numpy as np
import tempfile
from urllib.parse import quote
from pydub import AudioSegment
import csv
import pathlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import openai
import json
import logging
import time
import urllib3
from urllib3.util.retry import Retry
import sys  # Add sys for flushing output

# Configure the urllib3 connection pool globally with much larger limits
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Create a custom connection pool manager with larger pool sizes
http = urllib3.PoolManager(
    maxsize=100,  # Maximum number of connections in the pool
    block=False,  # Don't block when pool is full, just create new connections
    retries=Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
)

# Monkey patch requests to use our custom pool manager
import requests.adapters
original_init = requests.adapters.HTTPAdapter.__init__

def patched_init(self, *args, **kwargs):
    kwargs['pool_maxsize'] = 100
    kwargs['max_retries'] = 5
    kwargs['pool_block'] = False
    return original_init(self, *args, **kwargs)

requests.adapters.HTTPAdapter.__init__ = patched_init

# Configure logging to reduce Numba verbosity - disable completely
logging.basicConfig(level=logging.INFO)
# Completely disable Numba logging
logging.getLogger('numba').setLevel(logging.CRITICAL)
# Also disable other noisy loggers
logging.getLogger('numba.core').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.ssa').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.interpreter').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.byteflow').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.ir').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.typeinfer').setLevel(logging.CRITICAL)
logging.getLogger('numba.core.compiler').setLevel(logging.CRITICAL)

# Disable Numba JIT debug output
os.environ['NUMBA_DEBUG'] = '0'
os.environ['NUMBA_DISABLE_JIT'] = '0'
os.environ['NUMBA_VERBOSE'] = '0'

logger = logging.getLogger(__name__)

openai_client = None
def initialize_openai_client():
    """Initialize the OpenAI client with API key from environment variables."""
    global openai_client
    try:
        # Check if client is already initialized
        if openai_client:
            print("OpenAI client already initialized, reusing existing client")
            return openai_client
            
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("WARNING: OPENAI_API_KEY is not set")
            return None
            
        print("Initializing new OpenAI client...")
        openai_client = openai.OpenAI(api_key=api_key)
        print("OpenAI client initialized successfully")
        return openai_client
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        return None

def load_training_data():
    """Load training data from CSV file."""
    training_data = []
    csv_path = pathlib.Path(__file__).parent / 'training_data.csv'
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                moods = [mood.strip() for mood in row['moods'].split(',')]
                training_data.append({'song': row['song'],'artist': row['artist'],'lyrics': row['lyrics'], 'moods': moods,'tempo': row['tempo'],'energy': row['energy'],'brightness': row['brightness'],'zcr': row['zcr'],'contrast': row['contrast'],'chroma': row['chroma'],'flatness': row['flatness'],'rolloff': row['rolloff'],'mfcc1': row['mfcc1'],'mfcc2': row['mfcc2'],'mfcc3': row['mfcc3'],'mfcc4': row['mfcc4'],'mfcc5': row['mfcc5']})
        print(f"Loaded {len(training_data)} training examples from CSV")
        return training_data
    except Exception as e:
        print(f"Error loading training data: {e}")
        # Return minimal training data as fallback
        return [
            {"lyrics": "I'm so happy", "moods": ["happy"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so sad", "moods": ["sad"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so energetic", "moods": ["energetic"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so calm", "moods": ["calm"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so mad", "moods": ["mad"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so romantic", "moods": ["romantic"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so focused", "moods": ["focused"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0},
            {"lyrics": "I'm so mysterious", "moods": ["mysterious"],'tempo': 0,'energy': 0,'brightness': 0,'zcr': 0,'contrast': 0,'chroma': 0,'flatness': 0,'rolloff': 0,'mfcc1': 0,'mfcc2': 0,'mfcc3': 0,'mfcc4': 0,'mfcc5': 0}
        ]

# Load training data from CSV
training_data = load_training_data()

def create_genius_client():
    token = os.getenv('GENIUS_ACCESS_TOKEN')
    if token:
        print(f"[DEBUG] create_genius_client called. GENIUS_ACCESS_TOKEN is set")
    else:
        print(f"[DEBUG] create_genius_client called. GENIUS_ACCESS_TOKEN is not set")
    try:
        if not token:
            print("WARNING: GENIUS_ACCESS_TOKEN is not set")
            return None
        
        print("Creating Genius client with optimized connection pool...")
        genius = Genius(
            token,
            verbose=True,
            remove_section_headers=True,
            timeout=30,
            retries=3,  # Reduced from 5 to avoid overloading
            sleep_time=0.5,  # Reduced for speed while still respecting rate limits
        )
        
        # Override the genius client's session to use our configured adapter
        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_maxsize=100,
            max_retries=3,
            pool_block=False
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        genius._session = session
        
        print("Genius client created successfully with optimized connection pool")
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

def fetch_lyrics_with_vagalume(song_title, artist_name):
    """Fetch lyrics from Vagalume public API as a fallback if Genius fails."""
    try:
        print(f"[VAGALUME] Attempting to fetch lyrics for '{song_title}' by '{artist_name}'")
        base_url = "https://api.vagalume.com.br/search.php"
        params = {
            'art': artist_name,
            'mus': song_title
        }
        resp = requests.get(base_url, params=params, timeout=10)
        if resp.status_code != 200:
            print(f"[VAGALUME] API request failed: {resp.status_code}")
            return None
        data = resp.json()
        if 'type' in data and data['type'] == 'notfound':
            print(f"[VAGALUME] No lyrics found for '{song_title}' by '{artist_name}'")
            return None
        if 'mus' in data and len(data['mus']) > 0 and 'text' in data['mus'][0]:
            lyrics = data['mus'][0]['text']
            print(f"[VAGALUME] Successfully fetched lyrics for '{song_title}'")
            return lyrics
        print(f"[VAGALUME] No lyrics found in response for '{song_title}' by '{artist_name}'")
        return None
    except Exception as e:
        print(f"[VAGALUME] Error fetching lyrics: {e}")
        import traceback; traceback.print_exc()
        return None

def analyze_track(track, genius):
    """Extract audio features and lyrics from a track efficiently."""
    track_name = track['name']
    artist_name = track['artist']
    print(f"Analyzing track: {track_name} by {artist_name}")
    
    # Initialize with defaults
    audio_features = {
        'tempo': 0, 'energy': 0, 'brightness': 0, 'zcr': 0, 
        'contrast': 0, 'chroma': 0, 'flatness': 0, 'rolloff': 0,
        'mfcc1': 0, 'mfcc2': 0, 'mfcc3': 0, 'mfcc4': 0, 'mfcc5': 0
    }
    lyrics = ""
    
    # Create result dictionary immediately to avoid redundant copy operations
    result = track.copy()
    
    try:
        # Process lyrics first (while iTunes request is being made)
        # This is often faster than audio processing and can run in parallel
        if genius:
            lyrics = extract_lyrics_faster(track, genius)
            result['lyrics'] = lyrics
        
        # Process audio features
        preview_url = get_itunes_preview(track_name, artist_name)
        if preview_url:
            print(f"Found iTunes preview for {track_name}")
            audio_features = extract_audio_features(preview_url, track_name)
            result.update(audio_features)
        else:
            print(f"No iTunes preview found for {track_name}")
            result.update(audio_features)  # Use default features
        
        return result
        
    except Exception as e:
        print(f"Error analyzing track {track_name}: {e}")
        # Still return a track with at least the basic info so it doesn't get lost
        result['lyrics'] = lyrics
        result.update(audio_features)
        return result

def extract_audio_features(preview_url, track_name):
    """Extract audio features from a track preview URL."""
    audio_features = {
        'tempo': 0, 'energy': 0, 'brightness': 0, 'zcr': 0, 
        'contrast': 0, 'chroma': 0, 'flatness': 0, 'rolloff': 0,
        'mfcc1': 0, 'mfcc2': 0, 'mfcc3': 0, 'mfcc4': 0, 'mfcc5': 0
    }
    
    wav_path = None
    y = None
    sr = None
    
    try:
        wav_path = download_and_convert_preview(preview_url)
        if not wav_path:
            return audio_features
            
        # Use a lower SR for faster processing with minimal quality loss
        y, sr = librosa.load(wav_path, sr=22050)  # Lower sample rate for faster processing
        
        # Extract features
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        energy = float(np.mean(librosa.feature.rms(y=y)))
        
        # Use optimized computation methods - compute STFT once and reuse
        stft = np.abs(librosa.stft(y))
        
        # Calculate spectral features efficiently using the same STFT
        brightness = float(np.mean(librosa.feature.spectral_centroid(S=stft, sr=sr)))
        zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
        contrast = float(np.mean(librosa.feature.spectral_contrast(S=stft, sr=sr)))
        chroma = float(np.mean(librosa.feature.chroma_stft(S=stft, sr=sr)))
        flatness = float(np.mean(librosa.feature.spectral_flatness(S=stft)))
        rolloff = float(np.mean(librosa.feature.spectral_rolloff(S=stft, sr=sr)))

        # Calculate all MFCCs at once for efficiency
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=5)
        mfcc1 = float(np.mean(mfccs[0]))
        mfcc2 = float(np.mean(mfccs[1]))
        mfcc3 = float(np.mean(mfccs[2]))
        mfcc4 = float(np.mean(mfccs[3]))
        mfcc5 = float(np.mean(mfccs[4]))
        
        audio_features = {
            'tempo': tempo,
            'energy': energy,
            'brightness': brightness,
            'zcr': zcr,
            'contrast': contrast,
            'chroma': chroma,
            'flatness': flatness,
            'rolloff': rolloff,
            'mfcc1': mfcc1,
            'mfcc2': mfcc2,
            'mfcc3': mfcc3,
            'mfcc4': mfcc4,
            'mfcc5': mfcc5
        }
        
        return audio_features
        
    except Exception as e:
        print(f"Error extracting audio features: {e}")
        return audio_features
        
    finally:
        # Clean up resources
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)
        if y is not None:
            del y
        if sr is not None:
            del sr

def extract_lyrics_faster(track, genius):
    """Extract lyrics with faster approach - single attempt only."""
    try:
        if not genius:
            return ""
            
        print(f"Fetching lyrics for '{track['name']}' by '{track['artist']}'")
        
        # First try a clean search
        clean_title = track['name'].split('(')[0].strip().split('-')[0].strip()
        artist = track['artist']
        
        try:
            song = genius.search_song(clean_title, artist, get_full_info=False)
            if song and song.lyrics:
                return song.lyrics
        except Exception as e:
            print(f"Genius search failed: {e}")
            
        # If that fails, try Vagalume as fallback
        lyrics = fetch_lyrics_with_vagalume(clean_title, artist)
        if lyrics:
            return lyrics
            
        # Return empty string as fallback so we still process the track
        return ""
            
    except Exception as e:
        print(f"Error extracting lyrics: {e}")
        return ""

def analyze_user_library(sp, session=None):
    """Analyze a user's Spotify library in parallel."""
    print("Starting library analysis...")
    sys.stdout.flush()
    
    # Get the first 100 saved tracks from the user's library
    print("Fetching user's saved tracks...")
    sys.stdout.flush()
    results = sp.current_user_saved_tracks(limit=50)
    
    if not results or 'items' not in results:
        print("No tracks found in user's library")
        sys.stdout.flush()
        return {}, {}
        
    items = results['items']
    tracks = []
    
    print(f"Processing {len(items)} tracks...")
    sys.stdout.flush()
    
    for item in items:
        track = item['track']
        if track and 'id' in track:
            track_data = {
                'id': track['id'],
                'name': track['name'],
                'artist': track['artists'][0]['name'] if track['artists'] else "Unknown",
                'uri': track['uri']
            }
            tracks.append(track_data)
    
    if not tracks:
        print("No valid track data found")
        sys.stdout.flush()
        return {}, {}
        
    print(f"Extracted basic info for {len(tracks)} tracks")
    sys.stdout.flush()
    
    # Get a Genius client for lyrics fetching
    genius = create_genius_client()
    
    # Basic resource configuration for concurrent processing
    resources = {
        'cpu_count': os.cpu_count() or 2,
        # Use maximum threads for speed since we've configured the connection pool properly
        'thread_workers': min(32, max(4, (os.cpu_count() or 2) * 2))
    }
    
    print(f"System resources: {resources['cpu_count']} CPUs, thread workers: {resources['thread_workers']}")
    sys.stdout.flush()
    
    # Process tracks in parallel with ThreadPoolExecutor
    processed_tracks = []
    start_time = time.time()
    
    # Create batches of tracks for better load balancing
    batch_size = max(1, min(10, len(tracks) // resources['thread_workers']))
    batches = [tracks[i:i+batch_size] for i in range(0, len(tracks), batch_size)]
    print(f"Processing {len(batches)} batches of ~{batch_size} tracks each")
    sys.stdout.flush()
    
    # PHASE 1: Extract all lyrics and audio features in parallel
    print("\n=== PHASE 1: Extracting lyrics and audio features ===")
    sys.stdout.flush()
    with ThreadPoolExecutor(max_workers=resources['thread_workers']) as executor:
        # Submit all tracks for parallel processing
        futures = []
        for track in tracks:
            future = executor.submit(analyze_track, track, genius)
            futures.append(future)
            
        # Process results as they complete
        total = len(futures)
        completed = 0
        for future in as_completed(futures):
            completed += 1
            try:
                result = future.result()
                if result:
                    processed_tracks.append(result)
                    print(f"Completed {completed}/{total} tracks ({int(completed/total*100)}%)")
                    sys.stdout.flush()
            except Exception as e:
                print(f"Error processing track: {e}")
                sys.stdout.flush()
    
    elapsed = time.time() - start_time
    print(f"Completed extraction in {elapsed:.2f} seconds")
    sys.stdout.flush()
    
    # Ensure we have tracks to analyze
    if not processed_tracks:
        print("No tracks were successfully processed")
        sys.stdout.flush()
        return [], {}
        
    print(f"Successfully processed {len(processed_tracks)} tracks")
    sys.stdout.flush()
    
    # PHASE 2: Classify songs by mood using ChatGPT (after all tracks are processed)
    print("\n=== PHASE 2: Classifying songs by mood with ChatGPT ===")
    sys.stdout.flush()
    
    # Initialize the OpenAI client if not already done - only once all tracks are processed
    if not openai_client:
        print("Initializing OpenAI client for mood classification...")
        sys.stdout.flush()
        initialize_openai_client()
    
    # Analyze all tracks at once
    mood_data = analyze_with_chatgpt(processed_tracks, training_data)
    
    # Check if all tracks were classified
    track_ids = [str(track['id']) for track in processed_tracks]
    missing_track_ids = set(track_ids) - set(mood_data.keys())
    
    # If some tracks weren't classified, try again with just those tracks
    if missing_track_ids and len(missing_track_ids) < len(track_ids):
        print(f"\n{len(missing_track_ids)} tracks weren't classified. Making a second attempt for these tracks...")
        sys.stdout.flush()
        missing_tracks = [t for t in processed_tracks if str(t['id']) in missing_track_ids]
        second_attempt = analyze_with_chatgpt(missing_tracks, training_data)
        
        # Merge the results
        for track_id, moods in second_attempt.items():
            if track_id not in mood_data:
                mood_data[track_id] = moods
                print(f"Second attempt classified track {track_id} as {moods}")
                sys.stdout.flush()
    
    # Format the results for storage and API response
    analyzed_tracks = []
    mood_uris = {}
    
    # Process the mood classification results
    for track_id, track_moods in mood_data.items():
        # Find the matching track object
        track_obj = next((t for t in processed_tracks if str(t['id']) == str(track_id)), None)
        
        if track_obj and track_moods:
            # Create a streamlined track object with moods
            track_with_moods = {
                'id': track_obj['id'],
                'name': track_obj['name'],
                'artist': track_obj['artist'],
                'uri': track_obj['uri'],
                'moods': track_moods
            }
            analyzed_tracks.append(track_with_moods)
            
            # Group tracks by mood for easy retrieval (prevent duplicates using set)
            for mood in track_moods:
                if mood not in mood_uris:
                    mood_uris[mood] = set()  # Use set to prevent duplicates
                mood_uris[mood].add(track_obj['uri'])  # Add to set instead of append
    
    # Convert sets back to lists for JSON serialization
    for mood in mood_uris:
        mood_uris[mood] = list(mood_uris[mood])
    
    print(f"Final organization: {len(analyzed_tracks)} tracks grouped into {len(mood_uris)} moods")
    sys.stdout.flush()
    
    # Log simplified mood distribution as a dictionary/JSON object
    if mood_uris:
        mood_counts = {mood: len(uris) for mood, uris in mood_uris.items()}
        print(f"\nMood distribution: {json.dumps(mood_counts, indent=2)}")
        sys.stdout.flush()
        
        # Also log which tracks are in each mood for verification
        print("\n=== DETAILED MOOD BREAKDOWN ===")
        sys.stdout.flush()
        for mood, uris in mood_uris.items():
            track_names = []
            for uri in uris:
                track_obj = next((t for t in analyzed_tracks if t['uri'] == uri), None)
                if track_obj:
                    track_names.append(f"{track_obj['name']} by {track_obj['artist']}")
            print(f"{mood}: {len(uris)} tracks")
            sys.stdout.flush()
            for name in track_names:
                print(f"  - {name}")
                sys.stdout.flush()
        print("=" * 40)
        sys.stdout.flush()
    else:
        print("No mood distribution available - no tracks were classified")
        sys.stdout.flush()
    
    # Return both processed tracks and mood data
    return analyzed_tracks, mood_uris

def convert_numpy_to_python(obj):
    """Convert NumPy datatypes to Python native types for JSON serialization"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, dict):
        return {key: convert_numpy_to_python(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [convert_numpy_to_python(item) for item in obj]
    return obj

def analyze_with_chatgpt(tracks, training_data):
    """Send tracks to ChatGPT for mood analysis with improved diversity"""
    try:
        print(f"Analyzing {len(tracks)} tracks with ChatGPT")
        sys.stdout.flush()
        
        # Ensure OpenAI client is initialized
        if not openai_client:
            print("OpenAI client not initialized, initializing now...")
            sys.stdout.flush()
            initialize_openai_client()
            
        # Check if client was properly initialized
        if not openai_client:
            print("Error: OpenAI client not initialized")
            sys.stdout.flush()
            return {}
        else:
            print(f"Using OpenAI client: {type(openai_client).__name__}")
            sys.stdout.flush()
            
        # Select random examples for more diverse training
        training_examples = random.sample(training_data, min(5, len(training_data)))
        print(f"Selected {len(training_examples)} random training examples")
        sys.stdout.flush()
        
        # Prepare example data from training data for few-shot learning
        examples = []
        for i, example in enumerate(training_examples):
            examples.append({
                "id": f"example_{i}",
                "name": example.get('song', 'Unknown Song'),
                "artist": example.get('artist', 'Unknown Artist'),
                "lyrics": example.get('lyrics', ''),
                "audio_features": {
                    "tempo": float(example.get('tempo', 0)),
                    "energy": float(example.get('energy', 0)),
                    "brightness": float(example.get('brightness', 0)),
                    "zcr": float(example.get('zcr', 0)),
                    "contrast": float(example.get('contrast', 0)),
                    "chroma": float(example.get('chroma', 0)),
                    "flatness": float(example.get('flatness', 0)),
                    "rolloff": float(example.get('rolloff', 0)),
                    "mfcc1": float(example.get('mfcc1', 0)),
                    "mfcc2": float(example.get('mfcc2', 0)),
                    "mfcc3": float(example.get('mfcc3', 0)),
                    "mfcc4": float(example.get('mfcc4', 0)),
                    "mfcc5": float(example.get('mfcc5', 0))
                },
                "moods": example.get('moods', [])
            })
        
        # Prepare tracks data for analysis
        tracks_data = []
        track_ids = []  # Keep track of IDs to ensure all tracks are processed
        
        for track in tracks:
            # Don't skip tracks missing data - we want to analyze as many as possible
            if not track.get('id'):
                continue  # Only skip if ID is missing
                
            track_ids.append(str(track['id']))
                
            # Create a complete dictionary with all fields
            track_data = {
                "id": track['id'],
                "name": track.get('name', 'Unknown'),
                "artist": track.get('artist', 'Unknown'),
                "uri": track.get('uri', ''),
                "lyrics": track.get('lyrics', ''),
                "audio_features": {
                    "tempo": track.get('tempo', 0),
                    "energy": track.get('energy', 0),
                    "brightness": track.get('brightness', 0),
                    "zcr": track.get('zcr', 0),
                    "contrast": track.get('contrast', 0),
                    "chroma": track.get('chroma', 0),
                    "flatness": track.get('flatness', 0),
                    "rolloff": track.get('rolloff', 0),
                    "mfcc1": track.get('mfcc1', 0),
                    "mfcc2": track.get('mfcc2', 0),
                    "mfcc3": track.get('mfcc3', 0),
                    "mfcc4": track.get('mfcc4', 0),
                    "mfcc5": track.get('mfcc5', 0)
                }
            }
            tracks_data.append(track_data)
            
        if not tracks_data:
            print("No valid tracks to analyze")
            return {}
            
        # Convert NumPy arrays to Python native types for JSON serialization
        tracks_data = convert_numpy_to_python(tracks_data)
        examples = convert_numpy_to_python(examples)

        # Use the complete set of moods including mysterious and mad
        mood_list = ["happy", "sad", "energetic", "calm", "mad", "romantic", "mysterious", "focused"]

        prompt = f"""You are an expert music mood classifier with deep knowledge of emotional qualities in music across all genres.
Your task is to analyze songs based on audio features, lyrics, artist name, and song title, and assign the most appropriate mood(s) to each song.

Here are some example songs with their features and corresponding moods:
```json
{json.dumps(examples, indent=2)}
```

Now, analyze these songs and assign the most appropriate moods to each:
```json
{json.dumps(tracks_data, indent=2)}
```

For each song, assign one or more moods from this SPECIFIC list ONLY: {", ".join(mood_list)}

IMPORTANT CLASSIFICATION GUIDELINES:
1. EVERY song MUST have at least 1 mood assigned - NO exceptions
2. You MUST give equal consideration to ALL available moods
3. You MUST classify EVERY SINGLE song in the input list - do not skip any tracks
4. Use these precise mood definitions:
   - HAPPY: upbeat lyrics, major key, positive themes, joyful sound
   - SAD: melancholy lyrics, minor key, themes of loss or heartbreak
   - ENERGETIC: high tempo, high energy, upbeat rhythms, motivating lyrics
   - CALM: slow tempo, gentle instruments, peaceful lyrics, low intensity
   - MAD: aggressive lyrics, intense vocals, distorted sounds, heavy beats, angry themes, frustration, rebellion
   - ROMANTIC: love themes, emotional vocals, intimate feeling, relationship-focused
   - MYSTERIOUS: dark atmosphere, enigmatic lyrics, unusual chord progressions, creates a sense of intrigue or coolness, badass vibe
   - FOCUSED: steady rhythms, minimal vocal distractions, consistent patterns, productivity themes

5. Consider these audio feature correlations:
   - High tempo + high energy often indicates ENERGETIC or MAD
   - Low tempo + low energy often indicates CALM or SAD
   - High contrast + unusual harmonics may indicate MYSTERIOUS
   - Moderate tempo + high mfcc values may indicate FOCUSED
   - Emotional vocals + moderate tempo often indicates ROMANTIC

6. Pay special attention to lyrics - they often reveal the primary mood
7. For instrumental tracks or songs with minimal lyrics, rely more on audio features
8. Use your knowledge of music genres to help classify:
   - Heavy metal and punk often have MAD elements
   - Jazz and ambient often have CALM or MYSTERIOUS elements
   - Pop and dance often have HAPPY or ENERGETIC elements
   - Folk and acoustic often have SAD or ROMANTIC elements

9. You MUST classify EVERY song in the list - make your best educated guess based on the available information
10. If information is limited, use the track name, artist, and audio features to make an informed decision

Return your analysis as a JSON object with song IDs as keys and arrays of moods as values:
```json
{{
  "spotify_id_1": ["happy", "energetic"],
  "spotify_id_2": ["mysterious", "calm"],
  "spotify_id_3": ["mad", "energetic"]
}}
```
CRITICAL: Your response MUST include ALL song IDs that were provided in the input. Do not skip any songs.
"""

        # Call ChatGPT API with proper response format
        print("Sending request to OpenAI API...")
        sys.stdout.flush()
        start_time = time.time()
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert music mood classifier. You MUST classify EVERY song with at least one mood from the specified list ONLY. You MUST give EQUAL consideration to ALL possible moods including 'mad' and 'mysterious'. Every single song in the input MUST be included in your output with at least one mood. Make your best educated guess for each song based on all available information."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}  
        )
        elapsed = time.time() - start_time
        print(f"OpenAI API response received in {elapsed:.2f} seconds")
        sys.stdout.flush()
        
        # Parse response directly as JSON
        content = completion.choices[0].message.content
        if content is None:
            print("Error: Got None response from OpenAI")
            sys.stdout.flush()
            return {}
            
        try:
            print("Parsing OpenAI response as JSON...")
            sys.stdout.flush()
            moods_by_track = json.loads(content)
            # Ensure moods_by_track is a dictionary
            if not isinstance(moods_by_track, dict):
                print(f"Error: Expected dict response but got {type(moods_by_track)}")
                sys.stdout.flush()
                moods_by_track = {}
                
            print(f"Successfully analyzed moods for {len(moods_by_track)} tracks")
            sys.stdout.flush()
            
            # Log a sample of the classification results
            sample_size = min(5, len(moods_by_track))
            if sample_size > 0:
                print("\n=== SAMPLE CLASSIFICATION RESULTS ===")
                sys.stdout.flush()
                sample_items = list(moods_by_track.items())[:sample_size]
                for track_id, moods in sample_items:
                    track_obj = next((t for t in tracks if str(t['id']) == str(track_id)), None)
                    track_name = track_obj['name'] if track_obj else "Unknown"
                    artist = track_obj['artist'] if track_obj else "Unknown"
                    print(f"Track: {track_name} by {artist} → Moods: {', '.join(moods)}")
                    sys.stdout.flush()
                print("=" * 40)
                sys.stdout.flush()
            
            # Check for missing tracks - this is just for logging, not for fallback assignment
            missing_track_ids = set(track_ids) - set(str(id) for id in moods_by_track.keys())
            if missing_track_ids:
                print(f"Warning: {len(missing_track_ids)} tracks were not classified by OpenAI")
                sys.stdout.flush()
                for track_id in missing_track_ids:
                    track_obj = next((t for t in tracks if str(t['id']) == track_id), None)
                    if track_obj:
                        print(f"Missing classification for: {track_obj['name']} by {track_obj['artist']}")
                        sys.stdout.flush()
            
            # Create a result dictionary with proper string keys and validated moods
            result = {}
            
            # First ensure all track IDs in the response are strings
            for track_id, moods in moods_by_track.items():
                # Convert any non-string keys to strings
                str_id = str(track_id)
                
                # Validate moods are from the allowed list
                valid_moods = []
                if isinstance(moods, list):
                    for mood in moods:
                        if isinstance(mood, str) and mood.lower() in mood_list:
                            valid_moods.append(mood.lower())
                
                # Store valid moods (or empty list if none were valid)
                result[str_id] = valid_moods
                
            return result
            
        except Exception as e:
            print(f"Error processing ChatGPT response: {e}")
            import traceback; traceback.print_exc()
            return {}
        
    except Exception as e:
        print(f"Error in analyze_with_chatgpt: {e}")
        import traceback; traceback.print_exc()
        return {}

def get_tracks_for_mood(mood_uris, mood, limit=20):
    """Get up to 'limit' URIs for a mood from the session dict."""
    if not mood_uris:
        return []
    uris = mood_uris.get(mood.lower(), [])
    if not uris:
        return []
    return random.sample(uris, min(len(uris), limit))