# Spotify Mood Player

Select your current mood, and Spotify will play music based on that mood.

Deployed on Vercel at: https://spotify-mood-player.vercel.app/
(backend deployed on AWS Lambda)

**IMPORTANT:** This app is in Spotify Developer mode. Only whitelisted users can log in properly.

**UPDATES:** 
- Migrated hosting service from Fly.io for backend to AWS Lambda
- Migrated Fly.io-hosted MySQL database to PostgreSQL database on Supabase
- Refactored and improved classification algorithm using OpenAI API to better classify songs across all mood categories

## Features

- **Advanced Mood Analysis**
  - Multi-modal mood detection using few-shot learning with OpenAI API
  - Balanced classification across 8 distinct moods: happy, sad, energetic, calm, mad, romantic, focused, and mysterious
  - Audio feature extraction and analysis using Librosa

- **Smart Music Processing**
  - Parallel processing of user's Spotify library using ThreadPoolExecutor
  - Automatic audio feature extraction from iTunes previews
  - Fallback mechanisms for lyrics retrieval (Genius API + Vagalume)

- **User Experience**
  - Real-time Spotify playback control
  - Automatic library analysis on first login
  - Persistent mood-based track categorization
  - Responsive and modern UI with Spotify-inspired design

- **Technical Features**
  - Serverless architecture with AWS Lambda
  - PostgreSQL database on Supabase
  - RESTful API with proper CORS support
  - OAuth 2.0 authentication flow
  - Automatic database connection management
  - Health checks for service orchestration
  - CI/CD Pipelines for deployments

## Tech Stack

- Frontend: React, TypeScript, Vite, HTML, CSS, Vercel
- Backend: Flask, Python, AWS Lambda
- Database: PostgreSQL, Supabase
- APIs and Libraries: OpenAI API, iTunes Search API, Genius API, Spotify API, Librosa
- Build/Dev Tools: Vite, Node.js, npm, Cloudflare Tunnel

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
OPENAI_API_KEY=API key from OpenAI
SUPABASE_DATABASE_URL=get connection to postgres database in supabase
AWS_REGION=whatever region hosted on
AWS_ACCOUNT_ID=12 digit ID from dashboard
```

#### Frontend (`src/.env`)
```env
VITE_BACKEND_API_URL=http://127.0.0.1:5001/api (URL to your backend deployment)
```

### 3. Install & Run

#### Backend
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

### 4. Access the App

- Visit [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

## Few Shot Learning Data

- Lyrics are pre-cleaned: no leading/trailing spaces, no verse indicators, properly quoted, and all vulgarities/curse words are censored with asterisks.
- If you add new lyrics, ensure they follow this format for best results.

## Performance Features

- **Parallel Processing**: Uses ThreadPoolExecutor for concurrent track analysis
- **Database Connection Management**: Automatic retry logic for database connections
- **Memory Management**: Optimized resource usage and cleanup
- **API Rate Limiting**: Built-in delays to respect external API limits

## Production Limitations

**IMPORTANT:** In production, the mood categorization may not be fully accurate because the Genius API blocks requests from cloud hosting service IPs due to API abuse, terms of service violations (scraping), and legal/copyright restrictions. The categorization works best in:
- Local development environment
- When using a tunnel service (like Cloudflare) that routes through a residential IP to the production frontend

### Using Cloudflare Tunnel for Development

To use Cloudflare Tunnel for development:

1. Install Cloudflare:
```bash
brew install cloudflare/cloudflare/cloudflared
```

2. Create a quick tunnel to your local backend:
```bash
cloudflared tunnel --url http://127.0.0.1:5001
```

3. Use the provided `trycloudflare.com` domain to:
   - Set the `VITE_BACKEND_API_URL` environment variable in your deployed frontend
   - Set the `SPOTIPY_REDIRECT_URI` env variable in your local backend .env
   - Update the redirect URI in your Spotify Developer Dashboard

## Development Notes

- The backend uses Flask for API endpoints
- Database connections are automatically retried on startup
- Track analysis is parallelized for better performance
- Memory usage is optimized through batch processing
- API rate limits are respected with built-in delays
- OpenAI model not the best. doesn't understand mood nuance

## Challenges Overcome

During development, several significant challenges were encountered and resolved:

1. **CORS and Authentication**
   - Struggled to have session cookies transmitted between frontend and backend in production vs. local development, so implemented secure cookie-based token storage and authentication across different domains for CORS

2. **API Restrictions**
   - Worked around Spotify API development mode limitations by restricting users
   - Worked around Genius API restrictions by implementing fallback mechanisms for lyrics retrieval and tunneling with Cloudflare in production environments
   - Constantly ran into problems with API errors, so imlemented robust error handling and debugging statements

3. **Web Development Learning Curve**
   - Little to no prior experience with web dev, but mastered TypeScript and React

4. **Performance and Storage Optimization**
   - Faced with extremely slow sequential categorization, so implemented parrallel processing
   - Previously used Flask session cookies to store tracks, uris, and moods, but was unable to store a large amount of songs, so switched to a PostgreSQL relational database
   - I created a robust caching system that deletes all data that is no longer needed because of resource limitations from lack of funding.

## Lessons Learned

This project provided valuable learning opportunities in several areas:

1. **API Integration**
   - OAuth 2.0 flow implementation
   - Working with multiple third-party APIs
   - Handling API restrictions and rate limits
   - Implementing fallback mechanisms

2. **Backend Development**
   - Building REST APIs with CORS support
   - Managing relational databases with MySQL
   - Implementing parallel processing
   - Audio analysis and processing
   - Session management and security

3. **DevOps**
   - Setting up CI/CD pipelines
   - Containerization with Docker
   - Database management and migrations
   - Production deployment strategies
   - Environment configuration management

4. **Machine Learning**
   - Calibrating classification algorithms with different weights on features 
   - Feature engineering for mood detection in both audio and lyrics
   - Balancing multiple data sources with each other
   - Optimizing model performance
   - Implementing fallback mechanisms for missing data

5. **Frontend Development**
   - TypeScript and React best practices for modularization and interconnectedness
   - State management, data flow, and routing to endpoints and pages
   - Responsive design implementation

## Future Improvements

Planned enhancements to expand the project's capabilities:

1. **Enhanced User Experience**
   - Develop a comprehensive homepage
   - Expand page content and functionality
   - Add more interactive features
   - Implement user preferences and settings

2. **Production Readiness**
   - Migrate to a premium hosting service for less Genius API restriction and consistent uptime
   - Obtain proper Genius API authorization
   - Get Spotify API production approval to automatically authorize other userbases for scaling
   - Implement proper monitoring and logging

3. **Technical Enhancements**
   - Implement real-time progress tracking of analysis to sync progress/loading bar with actual analysis progress
   - Scale parallel processing capabilities
   - Optimize for larger music libraries that need to be analyzed (my library only has 40 songs)

4. **Feature Expansion**
   - Add multi-functional capabilities rather than just solely mood-based playback
   - Implement additional music analysis features
   - Create user profiles and preferences
   - Implement playlist generation based on mood combinations

5. **Analysis Improvements**
   - Enhance mood detection accuracy and expand training set (some songs are still categorized inaccurately because training set is relatively limited)
   - Add more mood categories with the ability to accurately categorize into the specific moods
   - Implement genre-based analysis

