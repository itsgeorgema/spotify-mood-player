import os
from lyricsgenius import Genius
import random
import requests
import tempfile
from urllib.parse import quote
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

# Heavy dependencies - imported lazily when needed
librosa = None
np = None
AudioSegment = None

def _import_heavy_dependencies():
    """Lazy import heavy dependencies only when needed"""
    global librosa, np, AudioSegment
    if librosa is None:
        try:
            import librosa as _librosa
            import numpy as _np
            from pydub import AudioSegment as _AudioSegment
            librosa = _librosa
            np = _np
            AudioSegment = _AudioSegment
            print("Successfully imported heavy dependencies (librosa, numpy, pydub)")
        except ImportError as e:
            print(f"Failed to import heavy dependencies: {e}")
            print("Audio analysis features will be disabled")
            return False
    return True

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
                # Handle both 'song' and 'song name' column names
                song_name = row.get('song') or row.get('song name', 'Unknown')
                moods = [mood.strip() for mood in row['moods'].split(',')]
                training_data.append({
                    'song': song_name,
                    'artist': row['artist'],
                    'lyrics': row['lyrics'], 
                    'moods': moods,
                    'tempo': float(row['tempo']) if row['tempo'] else 0,
                    'energy': float(row['energy']) if row['energy'] else 0,
                    'brightness': float(row['brightness']) if row['brightness'] else 0,
                    'zcr': float(row['zcr']) if row['zcr'] else 0,
                    'contrast': float(row['contrast']) if row['contrast'] else 0,
                    'chroma': float(row['chroma']) if row['chroma'] else 0,
                    'flatness': float(row['flatness']) if row['flatness'] else 0,
                    'rolloff': float(row['rolloff']) if row['rolloff'] else 0,
                    'mfcc1': float(row['mfcc1']) if row['mfcc1'] else 0,
                    'mfcc2': float(row['mfcc2']) if row['mfcc2'] else 0,
                    'mfcc3': float(row['mfcc3']) if row['mfcc3'] else 0,
                    'mfcc4': float(row['mfcc4']) if row['mfcc4'] else 0,
                    'mfcc5': float(row['mfcc5']) if row['mfcc5'] else 0
                })
        print(f"Loaded {len(training_data)} training examples from CSV")
        return training_data
    except Exception as e:
        print(f"Error loading training data: {e}")
        import traceback
        traceback.print_exc()
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
    if not _import_heavy_dependencies():
        print("Audio conversion not available - heavy dependencies not loaded")
        return None
        
    # At this point, AudioSegment is guaranteed to be imported
    assert AudioSegment is not None, "AudioSegment should be imported by now"
        
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
    
    if not _import_heavy_dependencies():
        print("Audio analysis not available - heavy dependencies not loaded")
        return audio_features
    
    # At this point, librosa and np are guaranteed to be imported
    assert librosa is not None and np is not None, "librosa and np should be imported by now"
    
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
    print("\n=== PHASE 2: Mood Classification ===")
    sys.stdout.flush()
    
    # Initialize the OpenAI client if not already done - only once all tracks are processed
    if not openai_client:
        initialize_openai_client()
    
    # Classify all tracks with persistent retry logic - KEEP TRYING UNTIL ALL ARE CLASSIFIED
    mood_data = classify_tracks_with_retry(processed_tracks, training_data)
    
    # Continue processing with whatever classifications we have (the retry function ensures maximum coverage)
    if not mood_data:
        print("WARNING: No tracks were classified by OpenAI after all attempts. Returning empty results.")
        sys.stdout.flush()
        return [], {}
    
    # Process all successfully classified tracks
    track_ids = [str(track['id']) for track in processed_tracks]
    classified_track_ids = set(mood_data.keys())
    missing_track_ids = set(track_ids) - classified_track_ids
    
    if missing_track_ids:
        print(f"NOTE: {len(missing_track_ids)} tracks were not classified after extensive retry attempts:")
        sys.stdout.flush()
        for track_id in list(missing_track_ids)[:5]:  # Show first 5
            track_obj = next((t for t in processed_tracks if str(t['id']) == track_id), None)
            if track_obj:
                print(f"  - {track_obj['name']} by {track_obj['artist']}")
                sys.stdout.flush()
        if len(missing_track_ids) > 5:
            print(f"  ... and {len(missing_track_ids) - 5} more")
            sys.stdout.flush()
        print("Continuing with successfully classified tracks...")
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
    
    # Always return results even if not all tracks were classified
    return analyzed_tracks, mood_uris

def convert_numpy_to_python(obj):
    """Convert NumPy datatypes to Python native types for JSON serialization"""
    # Only do numpy conversion if numpy is available
    if np is not None:
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

def classify_tracks_with_retry(tracks, training_data, max_retries=20):
    """Classify tracks with ChatGPT using retry logic until ALL tracks are classified - NEVER GIVE UP"""
    all_mood_data = {}
    remaining_tracks = tracks.copy()
    retry_count = 0
    
    print(f"Starting classification of {len(tracks)} tracks (will retry up to {max_retries} times until ALL are classified)")
    sys.stdout.flush()
    
    while remaining_tracks and retry_count < max_retries:
        retry_count += 1
        print(f"\n--- Attempt {retry_count}/{max_retries} for {len(remaining_tracks)} tracks ---")
        sys.stdout.flush()
        
        # Strategy: For later attempts, try smaller batches or individual tracks
        if retry_count > 10 and len(remaining_tracks) > 5:
            print("Using smaller batch strategy for better success rate...")
            sys.stdout.flush()
            batch_size = min(5, max(1, len(remaining_tracks) // 3))
            tracks_to_try = remaining_tracks[:batch_size]
        elif retry_count > 15:
            print("Trying individual track classification for maximum accuracy...")
            sys.stdout.flush()
            tracks_to_try = remaining_tracks[:1]  # Try one at a time
        else:
            tracks_to_try = remaining_tracks
        
        # Call ChatGPT with selected tracks
        attempt_results = analyze_with_chatgpt(tracks_to_try, training_data)
        
        if not attempt_results:
            print(f"Attempt {retry_count} failed - no classifications received, retrying...")
            sys.stdout.flush()
            continue
        
        # Process successful classifications
        newly_classified = []
        for track_id, moods in attempt_results.items():
            if track_id not in all_mood_data and moods:  # Only accept valid mood classifications
                all_mood_data[track_id] = moods
                newly_classified.append(track_id)
        
        print(f"Attempt {retry_count} successfully classified {len(newly_classified)} tracks")
        sys.stdout.flush()
        
        # Remove successfully classified tracks from remaining list
        remaining_tracks = [t for t in remaining_tracks if str(t['id']) not in newly_classified]
        
        if not remaining_tracks:
            print("✅ SUCCESS: All tracks successfully classified!")
            sys.stdout.flush()
            break
        else:
            print(f"Still need to classify {len(remaining_tracks)} tracks - continuing...")
            sys.stdout.flush()
            
            # Log which tracks still need classification
            for track in remaining_tracks[:3]:  # Show first 3
                print(f"  - {track.get('name', 'Unknown')} by {track.get('artist', 'Unknown')}")
                sys.stdout.flush()
            if len(remaining_tracks) > 3:
                print(f"  ... and {len(remaining_tracks) - 3} more")
                sys.stdout.flush()
    
    # If we still have unclassified tracks after max_retries, increase retries automatically
    if remaining_tracks and retry_count >= max_retries:
        print(f"\n🔄 Reached {max_retries} attempts but {len(remaining_tracks)} tracks still need classification")
        print("Switching to ULTRA-PERSISTENT mode with individual track classification...")
        sys.stdout.flush()
        
        # Try each remaining track individually with extended patience
        for track in remaining_tracks.copy():
            print(f"Individual classification attempt for: {track.get('name', 'Unknown')} by {track.get('artist', 'Unknown')}")
            sys.stdout.flush()
            
            # Try this track up to 5 times individually
            for individual_attempt in range(1, 6):
                single_track_result = analyze_with_chatgpt([track], training_data)
                if single_track_result and str(track['id']) in single_track_result:
                    all_mood_data[str(track['id'])] = single_track_result[str(track['id'])]
                    remaining_tracks.remove(track)
                    print(f"✅ Successfully classified {track.get('name', 'Unknown')} on individual attempt {individual_attempt}")
                    sys.stdout.flush()
                    break
                else:
                    print(f"Individual attempt {individual_attempt}/5 failed, retrying...")
                    sys.stdout.flush()
        
        # Final check after individual attempts
        if not remaining_tracks:
            print("✅ SUCCESS: All tracks finally classified using individual track strategy!")
            sys.stdout.flush()
        else:
            print(f"⚠️ {len(remaining_tracks)} tracks still unclassified after all strategies")
            sys.stdout.flush()
    
    # Final verification
    total_expected = len(tracks)
    total_classified = len(all_mood_data)
    
    if total_classified == total_expected:
        print(f"\n🎉 COMPLETE SUCCESS: All {total_expected} tracks classified successfully!")
        sys.stdout.flush()
    else:
        print(f"\n📊 Classification Results: {total_classified}/{total_expected} tracks classified ({(total_classified/total_expected)*100:.1f}% success rate)")
        sys.stdout.flush()
    
    return all_mood_data

def analyze_with_chatgpt(tracks, training_data):
    """Send tracks to ChatGPT for mood analysis - STRICT MODE (no fallbacks)"""
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
        training_examples = random.sample(training_data, min(15, len(training_data)))
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
            sys.stdout.flush()
            return {}
            
        # Clean up data before sending to OpenAI
        tracks_data = convert_numpy_to_python(tracks_data)
        
        # Create the prompt
        mood_list = ['happy', 'sad', 'mad', 'calm', 'romantic', 'energetic', 'focused', 'mysterious']
        
        prompt = f"""
You are an expert music mood classifier. Analyze the following songs and classify each with 1-3 moods from this EXACT list:
{mood_list}

Here are some training examples:
{json.dumps(examples, indent=2)}

Now classify these songs:
{json.dumps(tracks_data, indent=2)}

CRITICAL REQUIREMENTS:
1. ONLY use moods from the provided list: {mood_list}
2. Each song must have 1-3 moods (never 0, never more than 3)
3. You MUST classify EVERY SINGLE song in the input list - do not skip any tracks
4. Give EQUAL consideration to ALL moods including 'mad' and 'mysterious'
5. Base your classification on:
   - Lyrics (emotional content, themes, tone)
   - Audio features (tempo, energy, brightness, etc.)
   - Song title and artist context
   - Musical style and genre indicators
6. Consider the full emotional spectrum - not every song needs to be happy or energetic
7. For instrumental tracks or songs with minimal lyrics, rely more on audio features
8. 'mad' should be used for aggressive, angry, or intense tracks
9. 'mysterious' should be used for dark, atmospheric, or enigmatic tracks
10. You MUST classify EVERY song in the list - make your best educated guess based on the available information
11. If information is limited, use the track name, artist, and audio features to make an informed decision

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

        # Call ChatGPT API with proper response format and timeout handling
        print("Sending request to OpenAI API...")
        sys.stdout.flush()
        start_time = time.time()
        completion = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert music mood classifier. You MUST classify EVERY song with at least one mood from the specified list ONLY. You MUST give EQUAL consideration to ALL possible moods including 'mad' and 'mysterious'. Every single song in the input MUST be included in your output with at least one mood. Make your best educated guess for each song based on all available information."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            timeout=120  # 2 minute timeout
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
            
            # Log the raw response for debugging
            print(f"Raw OpenAI response length: {len(content)} characters")
            sys.stdout.flush()
            
            # Check if response looks like valid JSON
            if not content.strip():
                print("Error: Empty response from OpenAI")
                sys.stdout.flush()
                return {}
                
            if not (content.strip().startswith('{') and content.strip().endswith('}')):
                print("Error: Response doesn't appear to be valid JSON")
                print(f"Response starts with: {content[:100]}...")
                print(f"Response ends with: ...{content[-100:]}")
                sys.stdout.flush()
                return {}
            
            moods_by_track = json.loads(content)
            # Ensure moods_by_track is a dictionary
            if not isinstance(moods_by_track, dict):
                print(f"Error: Expected dict response but got {type(moods_by_track)}")
                sys.stdout.flush()
                return {}
                
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
            
            # Create a result dictionary with proper string keys and validated moods - STRICT MODE
            result = {}
            
            # Only accept tracks that have valid mood classifications
            for track_id, moods in moods_by_track.items():
                # Convert any non-string keys to strings
                str_id = str(track_id)
                
                # Validate moods are from the allowed list
                valid_moods = []
                if isinstance(moods, list):
                    for mood in moods:
                        if isinstance(mood, str) and mood.lower() in mood_list:
                            valid_moods.append(mood.lower())
                elif isinstance(moods, str) and moods.lower() in mood_list:
                    # Handle case where a single mood is returned as string instead of array
                    valid_moods.append(moods.lower())
                
                # STRICT MODE: Only accept tracks with valid moods - NO FALLBACKS
                if valid_moods:
                    result[str_id] = valid_moods
                else:
                    print(f"Warning: Track {str_id} had invalid moods: {moods}")
                    sys.stdout.flush()
                
            print(f"Strict validation result: {len(result)} tracks with valid mood classifications")
            sys.stdout.flush()
            
            # Report any tracks that weren't classified (for retry logic)
            classified_ids = set(result.keys())
            expected_ids = set(track_ids)
            missing_ids = expected_ids - classified_ids
            
            if missing_ids:
                print(f"Missing classifications for {len(missing_ids)} tracks (will retry)")
                sys.stdout.flush()
                for track_id in list(missing_ids)[:3]:  # Show first 3
                    track_obj = next((t for t in tracks if str(t['id']) == track_id), None)
                    if track_obj:
                        print(f"  - {track_obj['name']} by {track_obj['artist']}")
                        sys.stdout.flush()
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response from OpenAI: {e}")
            print(f"Response content (first 500 chars): {content[:500]}")
            print(f"Response content (last 500 chars): {content[-500:]}")
            sys.stdout.flush()
            
            # Try to extract partial JSON if possible
            try:
                # Look for the main JSON object in the response
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    partial_content = content[start_idx:end_idx+1]
                    print(f"Attempting to parse partial JSON: {partial_content[:200]}...")
                    sys.stdout.flush()
                    partial_result = json.loads(partial_content)
                    if isinstance(partial_result, dict):
                        print(f"Successfully parsed partial JSON with {len(partial_result)} tracks")
                        sys.stdout.flush()
                        return partial_result
            except:
                print("Failed to parse partial JSON as well")
                sys.stdout.flush()
                
            return {}
        except Exception as e:
            print(f"Unexpected error processing ChatGPT response: {e}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return {}
        
    except Exception as e:
        print(f"Error in analyze_with_chatgpt: {e}")
        import traceback; traceback.print_exc()
        
        # If it's a timeout error, provide a more helpful message
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            print("OpenAI API call timed out. This can happen with large track lists.")
            print("Consider running the analysis again or reducing the number of tracks.")
        
        return {}

def get_tracks_for_mood(mood_uris, mood, limit=20):
    """Get up to 'limit' URIs for a mood from the session dict."""
    if not mood_uris:
        return []
    uris = mood_uris.get(mood.lower(), [])
    if not uris:
        return []
    return random.sample(uris, min(len(uris), limit))