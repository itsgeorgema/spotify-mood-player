from dotenv import load_dotenv
import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
import time
import logging
import urllib.parse
import threading
from queue import Queue, Empty

logger = logging.getLogger(__name__)

# Load .env from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Import configuration
try:
    from config import get_config
    config = get_config()
except ImportError:
    # Fallback if config module is not available
    logger.warning("Could not import config module, using environment variables directly")
    config = None

# Global connection pool
connection_pool = None
_pool_lock = threading.Lock()

class ConnectionPool:
    """A simple connection pool implementation for better connection management."""
    
    def __init__(self, create_connection_func, max_connections=10, min_connections=2):
        self.create_connection = create_connection_func
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.pool = Queue(maxsize=max_connections)
        self.current_connections = 0
        self.lock = threading.Lock()
        
        # Pre-create minimum connections
        for _ in range(min_connections):
            try:
                conn = self.create_connection()
                if conn:
                    self.pool.put(conn)
                    self.current_connections += 1
                else:
                    logger.warning("Failed to create initial connection for pool")
            except Exception as e:
                logger.error(f"Error creating initial connection: {e}")
    
    def get_connection(self):
        """Get a connection from the pool."""
        try:
            # Try to get an existing connection
            conn = self.pool.get_nowait()
            # Test the connection
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return conn
            except Exception as e:
                logger.warning(f"Connection from pool is dead, creating new one: {e}")
                conn.close()
                self.current_connections -= 1
        except Empty:
            pass
        
        # Create a new connection if pool is empty or connection was dead
        with self.lock:
            if self.current_connections < self.max_connections:
                try:
                    conn = self.create_connection()
                    if conn:
                        self.current_connections += 1
                        return conn
                except Exception as e:
                    logger.error(f"Error creating new connection: {e}")
        
        # If we can't create a new connection, wait for one to become available
        try:
            conn = self.pool.get(timeout=10)
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                return conn
            except Exception as e:
                logger.warning(f"Connection from pool is dead: {e}")
                conn.close()
                self.current_connections -= 1
                return None
        except Empty:
            logger.error("Timeout waiting for connection from pool")
            return None
    
    def return_connection(self, conn):
        """Return a connection to the pool."""
        if conn is None:
            return
        
        try:
            # Test the connection before returning it
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.pool.put_nowait(conn)
        except Exception as e:
            logger.warning(f"Connection is dead, not returning to pool: {e}")
            try:
                conn.close()
            except:
                pass
            self.current_connections -= 1
    
    def close_connection(self, conn):
        """Close a connection and update the counter."""
        if conn is None:
            return
        
        try:
            conn.close()
        except Exception as e:
            logger.warning(f"Error closing connection: {e}")
        
        with self.lock:
            self.current_connections -= 1
    
    def close_all(self):
        """Close all connections in the pool."""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
        self.current_connections = 0

def init_database_config():
    """Initialize the database configuration."""
    global connection_pool
    
    with _pool_lock:
        if connection_pool is not None:
            logger.info("Database connection pool already initialized")
            return True
    
    try:
        # Get database URL from configuration or environment
        db_url = config.DATABASE_URL if config else os.getenv('SUPABASE_DATABASE_URL')
        
        if not db_url:
            logger.warning("No database URL found in configuration or environment variables")
            return False
        
        # Environment-specific connection handling
        is_serverless = os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None
        is_local_dev = os.getenv('FLASK_ENV') != 'production'
        
        # For serverless environments, use direct connection to avoid pooling issues
        if is_serverless and 'aws-0-' in db_url and ':6543' in db_url:
            # This is a transaction pooler URL, convert to direct connection for serverless
            db_url = db_url.replace(':6543', ':5432')
            logger.info("Converted transaction pooler URL to direct connection for serverless")
        
        # Parse the URL to extract connection parameters
        parsed_url = urllib.parse.urlparse(db_url)
        dbname = parsed_url.path[1:]  # Remove leading slash
        username = parsed_url.username
        password = parsed_url.password
        hostname = parsed_url.hostname
        port = parsed_url.port or 5432
        
        # Get configuration values
        timeout = config.DATABASE_TIMEOUT if config else (30 if is_serverless else 60)
        
        # Create a connection function with environment-specific settings
        def create_connection():
            try:
                # Build connection string
                conn_str = f"postgresql://{username}:{password}@{hostname}:{port}/{dbname}"
                
                # Configure SSL for production
                conn_params = {
                    'connect_timeout': timeout,
                    'application_name': 'spotify-mood-player'
                }
                
                if not is_local_dev:
                    conn_params['sslmode'] = 'require'
                
                conn = psycopg2.connect(conn_str, **conn_params)
                conn.autocommit = True  # Use autocommit mode for serverless
                return conn
            except Exception as e:
                logger.error(f"Error creating connection: {str(e)}")
                return None
        
        # Test the connection
        test_conn = create_connection()
        if not test_conn:
            logger.error("Failed to create test connection")
            return False
        
        try:
            with test_conn.cursor() as cursor:
                cursor.execute("SELECT 1")
            test_conn.close()
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
        
        # Get pool configuration
        if config:
            max_connections = config.DATABASE_POOL_SIZE
            min_connections = config.DATABASE_POOL_MIN
        else:
            # Fallback configuration
            max_connections = 2 if is_serverless else 10
            min_connections = 1 if is_serverless else 3
        
        # Create connection pool
        connection_pool = ConnectionPool(create_connection, max_connections, min_connections)
        
        logger.info(f"Database connection pool initialized successfully (max: {max_connections}, min: {min_connections})")
        return True
        
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
        connection = connection_pool.get_connection()
        return connection
    except Exception as e:
        logger.error(f"Error getting database connection: {str(e)}")
        return None

def close_db_connection(connection):
    """Close a database connection."""
    if connection is not None and connection_pool is not None:
        try:
            connection_pool.return_connection(connection)
        except Exception as e:
            logger.error(f"Error returning connection to pool: {str(e)}")
            # If returning to pool fails, close the connection
            connection_pool.close_connection(connection)

@contextmanager
def get_db_cursor():
    """Context manager for database cursor."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            yield cursor
            # No need to commit since we're using autocommit mode
        else:
            logger.error("Could not get database connection")
            yield None
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        if conn and not conn.autocommit:
            try:
                conn.rollback()
            except Exception as rollback_error:
                logger.error(f"Error during rollback: {rollback_error}")
        yield None
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                logger.error(f"Error closing cursor: {e}")
        if conn:
            close_db_connection(conn)

def get_or_create_user(user_id):
    """Get or create a user in the database."""
    with get_db_cursor() as cursor:
        if cursor is None:
            logger.error("Could not get database cursor in get_or_create_user")
            return None
            
        # Check if user exists
        try:
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Use raw SQL to avoid prepared statement issues
            select_sql = f"SELECT id FROM users WHERE spotify_id = '{safe_user_id}'"
            cursor.execute(select_sql)
            result = cursor.fetchone()
            
            if result:
                user_db_id = result['id']
                logger.debug(f"Found existing user with ID: {user_db_id}")
                return user_db_id
                
            # Create new user
            insert_sql = f"INSERT INTO users (spotify_id) VALUES ('{safe_user_id}') RETURNING id"
            cursor.execute(insert_sql)
            result = cursor.fetchone()
            
            if result:
                user_db_id = result['id']
                logger.info(f"Created new user with ID: {user_db_id}")
                return user_db_id
            else:
                logger.error("Failed to create new user")
                return None
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

def get_tracks_by_mood(user_id, mood, limit=20):
    """Get tracks for a user by mood."""
    with get_db_cursor() as cursor:
        if cursor is None:
            logger.error("Could not get database cursor in get_tracks_by_mood")
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
            
            logger.debug(f"Executing query: {query}")
            cursor.execute(query)
            result = cursor.fetchone()
            
            logger.debug(f"Query result type: {type(result)}, result: {result}")
            
            if result and result['track_uris']:
                track_uris = result['track_uris']
                logger.info(f"Found {len(track_uris)} tracks for mood '{mood}' for user '{user_id}'")
                return track_uris
            else:
                logger.info(f"No tracks found for mood '{mood}' for user '{user_id}'")
                return []
        except Exception as e:
            logger.error(f"Error in get_tracks_by_mood: {str(e)}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

def delete_tracks_for_user(user_id):
    """Delete all tracks for a user."""
    with get_db_cursor() as cursor:
        if cursor is None:
            return False
            
        try:
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Use raw SQL to avoid prepared statement issues
            delete_sql = f"DELETE FROM user_mood_tracks WHERE user_spotify_id = '{safe_user_id}'"
            cursor.execute(delete_sql)
            return True
        except Exception as e:
            logger.error(f"Error in delete_tracks_for_user: {str(e)}")
            return False

def delete_all_user_data(spotify_id):
    """Delete all user data from all tables including user record."""
    with get_db_cursor() as cursor:
        if cursor is None:
            return False
            
        try:
            # Escape single quotes for SQL safety
            safe_spotify_id = spotify_id.replace("'", "''")
            
            # Delete from user_mood_tracks table
            delete_tracks_sql = f"DELETE FROM user_mood_tracks WHERE user_spotify_id = '{safe_spotify_id}'"
            cursor.execute(delete_tracks_sql)
            mood_tracks_deleted = cursor.rowcount
            
            # Delete from tracks table (if it exists and has user-specific data)
            try:
                delete_tracks_table_sql = f"DELETE FROM tracks WHERE user_spotify_id = '{safe_spotify_id}'"
                cursor.execute(delete_tracks_table_sql)
                tracks_table_deleted = cursor.rowcount
            except Exception as e:
                # If tracks table doesn't exist or doesn't have user_spotify_id column, ignore
                logger.info(f"Tracks table deletion skipped: {str(e)}")
                tracks_table_deleted = 0
            
            # Delete from users table
            delete_user_sql = f"DELETE FROM users WHERE spotify_id = '{safe_spotify_id}'"
            cursor.execute(delete_user_sql)
            user_deleted = cursor.rowcount
            
            logger.info(f"Deleted {mood_tracks_deleted} mood track records, {tracks_table_deleted} track records, and {user_deleted} user record for spotify_id: {spotify_id}")
            return True
        except Exception as e:
            logger.error(f"Error in delete_all_user_data: {str(e)}")
            return False

def deduplicate_tracks_for_user(user_id):
    """Remove duplicate tracks within each mood for a user."""
    with get_db_cursor() as cursor:
        if cursor is None:
            logger.error("Could not get database cursor in deduplicate_tracks_for_user")
            return False
            
        try:
            # Escape single quotes for SQL safety
            safe_user_id = user_id.replace("'", "''")
            
            # Get all records for this user
            select_sql = f"""
                SELECT id, mood, track_uris FROM user_mood_tracks 
                WHERE user_spotify_id = '{safe_user_id}'
            """
            
            cursor.execute(select_sql)
            results = cursor.fetchall()
            
            if not results:
                logger.info(f"No tracks found for user {user_id}")
                return True
                
            duplicates_removed = 0
            
            for record in results:
                record_id = record['id']
                mood = record['mood']
                track_uris = record['track_uris']
                
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
                    
                    cursor.execute(update_sql)
                    logger.info(f"Removed {duplicates_in_mood} duplicates from mood '{mood}'")
                    
            if duplicates_removed > 0:
                logger.info(f"Successfully removed {duplicates_removed} duplicate tracks for user {user_id}")
            else:
                logger.info(f"No duplicates found for user {user_id}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error in deduplicate_tracks_for_user: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
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
        with get_db_cursor() as cursor:
            if cursor is None:
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
                    cursor.execute(delete_sql)
                    
                    # Convert Python list to PostgreSQL array format
                    # Escape single quotes in URIs
                    safe_uris = [uri.replace("'", "''") for uri in uris]
                    array_str = "ARRAY['" + "','".join(safe_uris) + "']"
                    
                    # Insert new records using raw SQL with proper array formatting
                    insert_sql = f"""
                    INSERT INTO user_mood_tracks (user_spotify_id, mood, track_uris, created_at)
                    VALUES ('{safe_user_id}', '{safe_mood}', {array_str}, NOW())
                    """
                    
                    cursor.execute(insert_sql)
                    
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
                if not init_database_config():
                    retries += 1
                    if retries < max_retries:
                        time.sleep(retry_interval)
                    continue
                
            conn = get_db_connection()
            if conn:
                close_db_connection(conn)
                logger.info("Database connection successful")
                return True
            else:
                raise Exception("Could not get connection from pool")
        except Exception as e:
            retries += 1
            logger.warning(f"Database connection attempt {retries} failed: {e}")
            if retries < max_retries:
                time.sleep(retry_interval)
    logger.error("Failed to connect to database after maximum retries")
    return False 