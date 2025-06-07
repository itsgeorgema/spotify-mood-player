# Spotify Mood Player

Select your current mood, and Spotify will play music based on that mood.

Deployed on Vercel at: https://spotify-mood-player.vercel.app/
(backend deployed on fly.io)

**IMPORTANT:** This app is in Spotify Developer mode. Only whitelisted users can log in properly.

## Features

- Mood-based Spotify playback using audio and lyrics analysis
- Multi-mood support (tracks can belong to several moods)
- Uses iTunes previews + Librosa to extract audio features
- Parallel processing for faster library analysis
- Automatic database connection management and retry logic

## Tech Stack

- Frontend: React, TypeScript, Vite, HTML, CSS
- Backend: Flask, Python
- Database: MySQL
- Infrastructure: Docker
- APIs and Libraries: iTunes Search API, Genius API, Spotify API, Librosa, ThreadPoolExecutor, Gevent, NLTK
- Build/Dev Tools: Vite, Node.js, npm

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/spotify-mood-player.git
cd spotify-mood-player
```

### 2. Environment Variables

#### Backend (`root/.env`)
```env
SPOTIPY_CLIENT_ID=your_spotify_client_id (get from Spotify for Developers)
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret (get from Spotify for Developers)
SPOTIPY_REDIRECT_URI=http://127.0.0.1:5001/api/callback (add to Spotify for Developers)
FLASK_SECRET_KEY=your_flask_secret (random string for Flask session encryption)
FRONTEND_URL=http://127.0.0.1:5173 (URL to your frontend deployment)
GENIUS_ACCESS_TOKEN=your_genius_token (get from Genius Developer Dashboard)
FLASK_ENV=development (production when deployed)
PORT=5001
MYSQL_HOST=mysql
MYSQL_USER=your_mysql_user (set your own username)
MYSQL_ROOT_PASSWORD=your_mysql_root_password (set when downloading MySQL)
MYSQL_PASSWORD=your_mysql_password (set your own)
MYSQL_DATABASE=your_db_name (set your own database name)
```

#### Frontend (`src/.env`)
```env
VITE_BACKEND_API_URL=http://127.0.0.1:5001/api (URL to your backend deployment)
```

### 3. Install & Run

#### Backend
- Download MySQL and set your root password, then download Docker Desktop. 
    - Docker Compose will be used to containerize backend and MySQL database service
    - Compose yml is already defined to containerize services and database schema is already defined
```bash
cd backend
docker compose up --build
#if not using Docker,
#pip install -r requirements.txt
```

#### Frontend
**in root directory (spotify-mood-player)
```bash
npm install
npm run dev
```

## Lyrics Training Data

- The backend uses a `training_data.csv` file for lyrics-based mood classification using naive bayes theorem probabilities
- Lyrics are pre-cleaned: no leading/trailing spaces, no verse indicators, properly quoted, and all vulgarities/curse words are censored with asterisks.
- If you add new lyrics, ensure they follow this format for best results.

## Performance Features

- **Parallel Processing**: Uses ThreadPoolExecutor for concurrent track analysis
- **Database Connection Management**: Automatic retry logic for database connections
- **Service Orchestration**: Docker Compose with health checks ensures proper startup order
- **Memory Management**: Batch processing with proper resource cleanup
- **API Rate Limiting**: Built-in delays to respect external API limits

## Development Notes

- The backend uses Gunicorn with Gevent workers for async processing
- Database connections are automatically retried on startup
- Track analysis is parallelized for better performance
- Memory usage is optimized through batch processing
- API rate limits are respected with built-in delays

### 4. Access the App

- Visit [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

### 5. Database

- If not using Docker Compose, setup schema manually in instance:
```bash
mysql -u root -p
# In the MySQL shell:
CREATE DATABASE your_db_name;
exit
# Then run:
mysql -u root -p your_db_name < mysql-init.sql
```
- Make sure your .env values match what you create in MySQL

---

## Notes

- Only whitelisted Spotify users can log in (see Spotify Developer Dashboard).
- To re-analyze your library, log out and log back in.
- For any issues, check backend and frontend logs.

