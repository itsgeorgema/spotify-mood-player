import os
import logging
import sys
import traceback
from db import get_db_connection, close_db_connection

logger = logging.getLogger(__name__)

def run_migrations():
    """Run database migrations to set up tables"""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Could not get database connection for migrations")
            return False
            
        # Create users table if it doesn't exist
        conn.run("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                spotify_id VARCHAR(255) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create user_mood_tracks table if it doesn't exist
        conn.run("""
            CREATE TABLE IF NOT EXISTS user_mood_tracks (
                id SERIAL PRIMARY KEY,
                user_spotify_id VARCHAR(255) NOT NULL,
                mood VARCHAR(100) NOT NULL,
                track_uris TEXT[] NOT NULL,
                created_at TIMESTAMP NOT NULL
            )
        """)
        
        # Add index on user_spotify_id and mood if it doesn't exist
        try:
            conn.run("""
                CREATE INDEX IF NOT EXISTS idx_user_mood_tracks_user_mood ON user_mood_tracks (user_spotify_id, mood)
            """)
        except Exception as e:
            # Some PostgreSQL versions don't support IF NOT EXISTS for indices
            # So we'll check if the error is about the index already existing
            if "already exists" not in str(e):
                raise
                
        logger.info("Database migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error running migrations: {e}")
        return False
    finally:
        if conn:
            close_db_connection(conn)

if __name__ == "__main__":
    run_migrations()
    print("Migrations script finished.") 