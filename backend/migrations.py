import logging
import sys
import traceback

logger = logging.getLogger(__name__)

def run_migrations():
    # Import here to avoid circular imports
    from db import get_db_connection, close_db_connection
    
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Add your migration SQL here - PostgreSQL syntax
            migrations = [
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    spotify_id VARCHAR(255) UNIQUE NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS tracks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    uri VARCHAR(255) NOT NULL,
                    mood VARCHAR(50) NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CONSTRAINT unique_track_mood UNIQUE (user_id, uri, mood)
                )
                """
            ]
            
            for migration in migrations:
                cursor.execute(migration)
            
            conn.commit()
            logger.info("Migrations completed successfully")
            print("Migrations completed successfully")
            sys.stdout.flush()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Migration failed: {str(e)}")
        print(f"Migration failed: {str(e)}")
        traceback.print_exc()
        sys.stdout.flush()
        raise
    finally:
        if conn is not None:
            close_db_connection(conn)

if __name__ == "__main__":
    run_migrations()
    print("Migrations script finished.") 