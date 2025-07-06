from dotenv import load_dotenv
import os
import pg8000.native
from contextlib import contextmanager
import time
import logging
import json
import urllib.parse

logger = logging.getLogger(__name__)

# Load .env from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Global connection pool
connection_pool = None

def init_database_config():
    """Initialize the database configuration."""
    global connection_pool
    
    try:
        # Get database URL from environment
        db_url = os.getenv('SUPABASE_DATABASE_URL')
        
        if not db_url:
            logger.warning("No database URL found in environment variables")
            return False
            
        # Parse the URL to extract connection parameters
        parsed_url = urllib.parse.urlparse(db_url)
        dbname = parsed_url.path[1:]  # Remove leading slash
        username = parsed_url.username
        password = parsed_url.password
        hostname = parsed_url.hostname
        port = parsed_url.port or 5432
        
        # Create a simple connection test function
        def get_connection():
            try:
                return pg8000.native.Connection(
                    user=username,
                    password=password,
                    host=hostname,
                    port=port,
                    database=dbname
                )
            except Exception as e:
                logger.error(f"Error creating connection: {str(e)}")
                return None
        
        # Test the connection
        conn = get_connection()
        if conn:
            conn.close()
            connection_pool = get_connection  # Store the function as our "pool"
            logger.info("Database connection tested successfully")
            return True
        else:
            logger.error("Failed to create test connection")
            return False
            
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

def get_db_connection():
    """Get a database connection from the pool."""
    global connection_pool
    
    if connection_pool is None:
        logger.error("Connection pool is not initialized")
        return None
        
    try:
        # connection_pool is actually a function in this case
        connection = connection_pool()
        return connection
    except Exception as e:
        logger.error(f"Error getting database connection: {str(e)}")
        return None

def close_db_connection(connection):
    """Close a database connection."""
    if connection is not None:
        try:
            connection.close()
        except Exception as e:
            logger.error(f"Error closing connection: {str(e)}")

@contextmanager
def get_db_cursor():
    """Context manager for database cursor."""
    conn = None
    try:
        conn = get_db_connection()
        if conn:
            yield conn  # With pg8000.native, the connection is the cursor
            conn.run("COMMIT")  # Use explicit SQL command instead of conn.commit()
        else:
            yield None
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if conn:
            conn.run("ROLLBACK")  # Use explicit SQL command instead of conn.rollback()
        yield None
    finally:
        if conn:
            close_db_connection(conn)

def get_or_create_user(user_id):
    """Get or create a user in the database."""
    with get_db_cursor() as conn:
        if conn is None:
            return None
            
        # Check if user exists
        try:
            result = conn.run("SELECT id FROM users WHERE spotify_id = :spotify_id", spotify_id=user_id)
            if result:
                return result[0][0]
                
            # Create new user
            result = conn.run(
                "INSERT INTO users (spotify_id) VALUES (:spotify_id) RETURNING id",
                spotify_id=user_id
            )
            return result[0][0] if result else None
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            return None

def get_tracks_by_mood(user_id, mood, limit=20):
    """Get tracks for a user by mood."""
    with get_db_cursor() as conn:
        if conn is None:
            return []
            
        try:
            result = conn.run(
                """
                SELECT track_uris FROM user_mood_tracks 
                WHERE user_spotify_id = :user_id AND mood = :mood
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id=user_id, 
                mood=mood
            )
            
            if result and result[0][0]:
                return result[0][0]
            return []
        except Exception as e:
            logger.error(f"Error in get_tracks_by_mood: {str(e)}")
            return []

def delete_tracks_for_user(user_id):
    """Delete all tracks for a user."""
    with get_db_cursor() as conn:
        if conn is None:
            return False
            
        try:
            conn.run(
                "DELETE FROM user_mood_tracks WHERE user_spotify_id = :user_id",
                user_id=user_id
            )
            return True
        except Exception as e:
            logger.error(f"Error in delete_tracks_for_user: {str(e)}")
            return False

def insert_tracks(user_id, tracks):
    """Insert analyzed tracks for a user."""
    if not tracks or not user_id:
        return False
        
    try:
        # Create mood buckets
        mood_uris = {}
        
        # Process tracks and organize by mood
        for track in tracks:
            if not track.get('moods'):
                continue
                
            for mood in track.get('moods', []):
                if mood not in mood_uris:
                    mood_uris[mood] = []
                    
                if track.get('uri'):
                    mood_uris[mood].append(track['uri'])
        
        # Insert each mood separately with its own connection to avoid prepared statement conflicts
        for mood, uris in mood_uris.items():
            if not uris:
                continue
                
            # Use a fresh connection for each insert to avoid prepared statement conflicts
            with get_db_cursor() as conn:
                if conn is None:
                    logger.error(f"Failed to get database connection for mood: {mood}")
                    continue
                    
                try:
                    # Delete existing records for this user and mood first
                    conn.run(
                        "DELETE FROM user_mood_tracks WHERE user_spotify_id = :user_id AND mood = :mood",
                        user_id=user_id,
                        mood=mood
                    )
                    
                    # Insert new records
                    conn.run(
                        """
                        INSERT INTO user_mood_tracks 
                        (user_spotify_id, mood, track_uris, created_at)
                        VALUES (:user_id, :mood, :track_uris, NOW())
                        """,
                        user_id=user_id,
                        mood=mood,
                        track_uris=uris
                    )
                    logger.info(f"Successfully inserted {len(uris)} tracks for mood '{mood}'")
                    
                except Exception as e:
                    logger.error(f"Error inserting tracks for mood '{mood}': {str(e)}")
                    # Continue with other moods even if one fails
                    continue
                
        return True
        
    except Exception as e:
        logger.error(f"Error in insert_tracks: {str(e)}")
        return False

def wait_for_db(max_retries=30, retry_interval=2):
    """Wait for database to be ready with retries."""
    retries = 0
    while retries < max_retries:
        try:
            # Initialize config first if needed
            if not connection_pool:
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