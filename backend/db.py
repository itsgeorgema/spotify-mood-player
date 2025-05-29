from dotenv import load_dotenv
import os
import mysql.connector

# Load .env from the root directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('MYSQL_HOST'),
        user=os.getenv('MYSQL_USER'),
        password=os.getenv('MYSQL_PASSWORD'),
        database=os.getenv('MYSQL_DATABASE')
    )

def get_or_create_user(spotify_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE spotify_id=%s", (spotify_id,))
    result = cursor.fetchone()
    if result:
        user_id = result[0]
    else:
        cursor.execute("INSERT INTO users (spotify_id) VALUES (%s)", (spotify_id,))
        conn.commit()
        user_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return user_id

def insert_tracks(user_id, tracks):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracks WHERE user_id=%s", (user_id,))
    for track in tracks:
        # Support multi-mood: insert one row per (track, mood)
        moods = track.get('moods')
        if moods:
            for mood in moods:
                cursor.execute(
                    "INSERT INTO tracks (user_id, uri, mood) VALUES (%s, %s, %s)",
                    (user_id, track['uri'], mood)
                )
        else:
            # fallback for legacy single-mood tracks
            cursor.execute(
                "INSERT INTO tracks (user_id, uri, mood) VALUES (%s, %s, %s)",
                (user_id, track['uri'], track.get('mood', 'unknown'))
            )
    conn.commit()
    cursor.close()
    conn.close()

def get_tracks_by_mood(user_id, mood, limit=20):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT uri FROM tracks WHERE user_id=%s AND mood=%s LIMIT %s",
        (user_id, mood, limit)
    )
    rows = cursor.fetchall() or []
    uris = [row[0] for row in rows]
    cursor.close()
    conn.close()
    return uris

def delete_tracks_for_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tracks WHERE user_id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close() 