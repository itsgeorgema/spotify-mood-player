from dotenv import load_dotenv
import os
import psycopg2
from psycopg2 import sql
import time
import logging

logger = logging.getLogger(__name__)

# Load .env from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Global connection configuration
db_config = {
    'initialized': False,
    'db_url': None,
    'connection_params': {
        'connect_timeout': 10,
        'application_name': 'spotify-mood-player',
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5
    },
    'connection_components': {}
}

def init_database_config():
    """Initialize database connection parameters (but don't create connections yet)"""
    global db_config
    try:
        # Try Supabase URL first (preferred for serverless)
        db_url = os.getenv('SUPABASE_DATABASE_URL')
        
        # If Supabase URL is not available, try to build connection from individual params
        if not db_url:
            logger.info("SUPABASE_DATABASE_URL not found, trying local PostgreSQL connection parameters")
            host = os.getenv('POSTGRES_HOST', 'postgres')  # Default to service name in docker-compose
            user = os.getenv('POSTGRES_USER', 'postgres')
            password = os.getenv('POSTGRES_PASSWORD', 'postgres')
            db_name = os.getenv('POSTGRES_DB', 'postgres')
            port = os.getenv('POSTGRES_PORT', '5432')
            
            # Instead of using string formatting, store individual components
            db_config['connection_components'] = {
                'host': host,
                'user': user,
                'password': password,
                'dbname': db_name,
                'port': port
            }
            # Set db_url to None to use components instead
            db_url = None
        
        # Store connection info
        db_config['db_url'] = db_url
        
        # Add connection parameters from env vars if available
        db_config['connection_params']['connect_timeout'] = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
        
        # Log connection (hide credentials)
        if db_url:
            url_parts = db_url.split('@')
            if len(url_parts) > 1:
                auth_part = url_parts[0].split('://')
                protocol = auth_part[0] if len(auth_part) > 1 else ''
                masked_url = f"{protocol}://****:****@{url_parts[1]}"
                logger.info(f"Database configured with: {masked_url}")
            else:
                logger.info("Database configuration initialized")
        else:
            logger.info(f"Database configured with components: host={db_config['connection_components'].get('host')}, port={db_config['connection_components'].get('port')}, dbname={db_config['connection_components'].get('dbname')}")
            
        db_config['initialized'] = True
        return True
    except Exception as e:
        logger.error(f"Error initializing database config: {e}")
        db_config['initialized'] = False
        return False

def get_db_connection():
    """Get a fresh database connection for each request (optimized for serverless environment)"""
    global db_config
    
    # Initialize connection parameters if not already done
    if not db_config['initialized']:
        init_database_config()
    
    if not db_config['initialized'] or not db_config['db_url']:
        raise Exception("Database not properly configured")
    
    # Try to establish a connection with retry logic
    max_retries = 3
    retry_delay = 1  # Start with 1 second delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # Create a new connection with serverless-optimized parameters
            if db_config['db_url']:
                # Use connection string if available
                conn = psycopg2.connect(
                    db_config['db_url'],
                    **db_config['connection_params']
                )
            else:
                # Use connection parameters if URL is not available
                conn = psycopg2.connect(
                    **db_config['connection_components'],
                    **db_config['connection_params']
                )
            
            # Set session parameters optimized for serverless/short-lived connections
            with conn.cursor() as cursor:
                # Set statement timeout to avoid hanging connections
                cursor.execute("SET statement_timeout = '30s'")
                # Test connection is working
                cursor.execute("SELECT 1")
            
            return conn
            
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                logger.warning(f"Database connection attempt {attempt + 1} failed: {e}, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 5)  # Exponential backoff, max 5 sec
    
    # If we get here, all attempts failed
    logger.error(f"Failed to connect to database after {max_retries} attempts: {last_error}")
    if last_error:
        raise last_error
    else:
        raise Exception("Failed to establish database connection")

def close_db_connection(conn):
    """Close a database connection safely"""
    if conn:
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing database connection: {e}")

def wait_for_db(max_retries=30, retry_interval=2):
    """Wait for database to be ready with retries."""
    retries = 0
    while retries < max_retries:
        try:
            # Initialize config first if needed
            if not db_config['initialized']:
                init_database_config()
                
            conn = get_db_connection()
            close_db_connection(conn)
            logger.info("Database connection successful")
            return True
        except Exception as e:
            retries += 1
            logger.warning(f"Database connection attempt {retries} failed: {e}")
            if retries < max_retries:
                time.sleep(retry_interval)
    logger.error("Failed to connect to database after maximum retries")
    return False

def get_or_create_user(spotify_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE spotify_id = %s", (spotify_id,))
            result = cursor.fetchone()
            if result:
                user_id = result[0]
            else:
                cursor.execute(
                    "INSERT INTO users (spotify_id) VALUES (%s) RETURNING id", 
                    (spotify_id,)
                )
                inserted = cursor.fetchone()
                if not inserted:
                    raise Exception("Failed to insert user")
                user_id = inserted[0]
                conn.commit()
        return user_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in get_or_create_user: {e}")
        raise
    finally:
        close_db_connection(conn)

def insert_tracks(user_id, tracks):
    """Insert or update tracks with their moods in the database.
    
    Args:
        user_id (int): The database user ID
        tracks (list): List of track dictionaries, each with 'uri' and 'moods' fields
    """
    if not tracks:
        print("No tracks provided to insert_tracks")
        return
        
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Delete existing tracks for this user
            cursor.execute("DELETE FROM tracks WHERE user_id = %s", (user_id,))
            
            # Prepare data for batch insert
            batch_values = []
            for track in tracks:
                # Get moods from the track data
                moods = track.get('moods', [])
                if not moods:
                    # Try legacy 'mood' field if 'moods' not found
                    legacy_mood = track.get('mood')
                    if legacy_mood:
                        moods = [legacy_mood]
                        
                # Skip tracks with no mood data
                if not moods:
                    continue
                    
                uri = track.get('uri')
                if not uri:
                    continue
                    
                # Insert one row per mood for this track
                for mood in moods:
                    if mood and isinstance(mood, str):
                        batch_values.append((user_id, uri.strip(), mood.lower().strip()))
            
            # Execute batch insert if we have values
            if batch_values:
                args = ','.join(cursor.mogrify("(%s,%s,%s)", i).decode('utf-8') for i in batch_values)
                query = "INSERT INTO tracks (user_id, uri, mood) VALUES " + args
                cursor.execute(query)
                
            # Commit the transaction
            conn.commit()
            print(f"Successfully stored {len(batch_values)} track-mood pairs for user {user_id}")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error inserting tracks: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            close_db_connection(conn)

def get_tracks_by_mood(user_id, mood, limit=20):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT uri FROM tracks WHERE user_id = %s AND mood = %s LIMIT %s",
                (user_id, mood, limit)
            )
            rows = cursor.fetchall() or []
            uris = [row[0] for row in rows]
        return uris
    except Exception as e:
        logger.error(f"Error in get_tracks_by_mood: {e}")
        return []
    finally:
        close_db_connection(conn)

def delete_tracks_for_user(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tracks WHERE user_id = %s", (user_id,))
            conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error in delete_tracks_for_user: {e}")
    finally:
        close_db_connection(conn) 