from db import get_db_connection
import logging

logger = logging.getLogger(__name__)

def run_migrations():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Add your migration SQL here
        migrations = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                spotify_id VARCHAR(255) UNIQUE NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                uri VARCHAR(255) NOT NULL,
                mood VARCHAR(50) NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE KEY unique_track_mood (user_id, uri, mood)
            )
            """
        ]
        
        for migration in migrations:
            cursor.execute(migration)
        
        conn.commit()
        logger.info("Migrations completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    run_migrations()
    print("Migrations script finished.") 