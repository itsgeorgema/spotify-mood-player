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
        
        # For Supabase serverless, we need to use the direct connection URL, not the transaction pooler
        # If using transaction pooler, replace with direct connection
        if 'aws-0-' in db_url and ':6543' in db_url:
            # This is a transaction pooler URL, convert to direct connection
            db_url = db_url.replace(':6543', ':5432')
            logger.info("Converted transaction pooler URL to direct connection")
            
        # Parse the URL to extract connection parameters
        parsed_url = urllib.parse.urlparse(db_url)
        dbname = parsed_url.path[1:]  # Remove leading slash
        username = parsed_url.username
        password = parsed_url.password
        hostname = parsed_url.hostname
        port = parsed_url.port or 5432
        
        # Create a connection function with serverless-optimized settings
        def get_connection():
            try:
                return pg8000.native.Connection(
                    user=username,
                    password=password,
                    host=hostname,
                    port=port,
                    database=dbname,
                    # Set shorter timeout for serverless (pg8000 uses 'timeout' parameter)
                    timeout=30
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
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Use raw SQL to avoid prepared statement issues
            select_sql = f"SELECT id FROM users WHERE spotify_id = '{safe_user_id}'"
            result = conn.run(select_sql)
            
            if result:
                return result[0][0]
                
            # Create new user
            insert_sql = f"INSERT INTO users (spotify_id) VALUES ('{safe_user_id}') RETURNING id"
            result = conn.run(insert_sql)
            
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
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            safe_mood = mood.replace("'", "''")
            
            # Use raw SQL to avoid prepared statement issues
            query = f"""
                SELECT track_uris FROM user_mood_tracks 
                WHERE user_spotify_id = '{safe_user_id}' AND mood = '{safe_mood}'
                ORDER BY created_at DESC
                LIMIT 1
            """
            
            result = conn.run(query)
            
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
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Use raw SQL to avoid prepared statement issues
            delete_sql = f"DELETE FROM user_mood_tracks WHERE user_spotify_id = '{safe_user_id}'"
            conn.run(delete_sql)
            return True
        except Exception as e:
            logger.error(f"Error in delete_tracks_for_user: {str(e)}")
            return False

def deduplicate_tracks_for_user(user_id):
    """Remove duplicate tracks within each mood for a user."""
    with get_db_cursor() as conn:
        if conn is None:
            return False
            
        try:
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Get all records for this user
            select_sql = f"""
                SELECT id, mood, track_uris FROM user_mood_tracks 
                WHERE user_spotify_id = '{safe_user_id}'
            """
            
            results = conn.run(select_sql)
            
            if not results:
                logger.info(f"No tracks found for user {user_id}")
                return True
                
            duplicates_removed = 0
            
            for record in results:
                record_id, mood, track_uris = record
                
                if not track_uris:
                    continue
                    
                # Convert to set to remove duplicates, then back to list
                original_count = len(track_uris)
                unique_uris = list(set(track_uris))
                
                if len(unique_uris) < original_count:
                    duplicates_in_mood = original_count - len(unique_uris)
                    duplicates_removed += duplicates_in_mood
                    
                    # Update the record with deduplicated URIs
                    safe_uris = [uri.replace("'", "''") for uri in unique_uris]
                    array_str = "ARRAY['" + "','".join(safe_uris) + "']"
                    
                    update_sql = f"""
                        UPDATE user_mood_tracks 
                        SET track_uris = {array_str}
                        WHERE id = {record_id}
                    """
                    
                    conn.run(update_sql)
                    logger.info(f"Removed {duplicates_in_mood} duplicates from mood '{mood}'")
                    
            if duplicates_removed > 0:
                logger.info(f"Successfully removed {duplicates_removed} duplicate tracks for user {user_id}")
            else:
                logger.info(f"No duplicates found for user {user_id}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error in deduplicate_tracks_for_user: {str(e)}")
            return False

def insert_tracks(user_id, tracks):
    """Insert analyzed tracks for a user."""
    if not tracks or not user_id:
        return False
        
    try:
        # Create mood buckets using sets to prevent duplicates
        mood_uris = {}
        total_track_mood_pairs = 0
        
        # Process tracks and organize by mood
        for track in tracks:
            if not track.get('moods'):
                continue
                
            for mood in track.get('moods', []):
                if mood not in mood_uris:
                    mood_uris[mood] = set()  # Use set to prevent duplicates
                    
                if track.get('uri'):
                    initial_count = len(mood_uris[mood])
                    mood_uris[mood].add(track['uri'])  # Use add() instead of append()
                    total_track_mood_pairs += 1
                    
                    # Log if this was a duplicate (set size didn't change)
                    if len(mood_uris[mood]) == initial_count:
                        logger.info(f"Prevented duplicate: '{track.get('name', 'Unknown')}' already exists in mood '{mood}'")
        
        if not mood_uris:
            logger.warning("No mood data to insert")
            return False
            
        # Calculate deduplication stats
        total_unique_tracks = sum(len(uris_set) for uris_set in mood_uris.values())
        duplicates_prevented = total_track_mood_pairs - total_unique_tracks
        
        if duplicates_prevented > 0:
            logger.info(f"Duplicate prevention: {duplicates_prevented} duplicate track-mood pairs prevented")
            logger.info(f"Track-mood pairs: {total_track_mood_pairs} total → {total_unique_tracks} unique")
            
        # Use single connection for all operations
        with get_db_cursor() as conn:
            if conn is None:
                logger.error("Failed to get database connection")
                return False
                
            successful_insertions = 0
            total_moods = len(mood_uris)
            
            for mood, uris_set in mood_uris.items():
                if not uris_set:
                    continue
                    
                try:
                    # Convert set to list to maintain order and enable indexing
                    uris = list(uris_set)
                    
                    # Escape single quotes in user_id and mood for SQL safety
                    safe_user_id = user_id.replace("'", "''")
                    safe_mood = mood.replace("'", "''")
                    
                    # Delete existing records for this user and mood first using raw SQL
                    delete_sql = f"DELETE FROM user_mood_tracks WHERE user_spotify_id = '{safe_user_id}' AND mood = '{safe_mood}'"
                    conn.run(delete_sql)
                    
                    # Convert Python list to PostgreSQL array format
                    # Escape single quotes in URIs
                    safe_uris = [uri.replace("'", "''") for uri in uris]
                    array_str = "ARRAY['" + "','".join(safe_uris) + "']"
                    
                    # Insert new records using raw SQL with proper array formatting
                    insert_sql = f"""
                    INSERT INTO user_mood_tracks (user_spotify_id, mood, track_uris, created_at)
                    VALUES ('{safe_user_id}', '{safe_mood}', {array_str}, NOW())
                    """
                    
                    conn.run(insert_sql)
                    
                    logger.info(f"Successfully inserted {len(uris)} tracks for mood '{mood}'")
                    successful_insertions += 1
                    
                except Exception as e:
                    logger.error(f"Error inserting tracks for mood '{mood}': {e}")
                    # Continue with other moods even if one fails
                    continue
                    
            # Consider it successful if at least half the moods were inserted
            success_threshold = max(1, total_moods // 2)
            if successful_insertions >= success_threshold:
                logger.info(f"Database insertion successful: {successful_insertions}/{total_moods} moods inserted")
                return True
            else:
                logger.warning(f"Database insertion partially failed: only {successful_insertions}/{total_moods} moods inserted")
                return False
        
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