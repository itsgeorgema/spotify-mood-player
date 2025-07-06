import os
import logging

logger = logging.getLogger(__name__)

class Config:
    """Base configuration class with common settings."""
    
    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database settings
    DATABASE_URL = os.getenv('SUPABASE_DATABASE_URL')
    DATABASE_POOL_SIZE = int(os.getenv('DATABASE_POOL_SIZE', '10'))
    DATABASE_POOL_MIN = int(os.getenv('DATABASE_POOL_MIN', '3'))
    DATABASE_TIMEOUT = int(os.getenv('DATABASE_TIMEOUT', '60'))
    
    # Spotify API settings
    SPOTIFY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
    SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIPY_CLIENT_SECRET')
    SPOTIFY_REDIRECT_URI = os.getenv('SPOTIPY_REDIRECT_URI')
    
    # External API settings
    GENIUS_ACCESS_TOKEN = os.getenv('GENIUS_ACCESS_TOKEN')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Frontend settings
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'https://spotify-mood-player.vercel.app')
    
    # Server settings
    PORT = int(os.getenv('PORT', '5001'))
    HOST = os.getenv('HOST', '0.0.0.0')
    
    @classmethod
    def validate_required_config(cls):
        """Validate that all required configuration is present."""
        required_vars = [
            ('DATABASE_URL', cls.DATABASE_URL),
            ('SPOTIFY_CLIENT_ID', cls.SPOTIFY_CLIENT_ID),
            ('SPOTIFY_CLIENT_SECRET', cls.SPOTIFY_CLIENT_SECRET),
            ('SPOTIFY_REDIRECT_URI', cls.SPOTIFY_REDIRECT_URI),
        ]
        
        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
            return False
        
        return True
    
    @classmethod
    def get_environment_info(cls):
        """Get information about the current environment."""
        return {
            'is_production': os.getenv('FLASK_ENV') == 'production',
            'is_lambda': os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None,
            'is_local_dev': os.getenv('FLASK_ENV') != 'production',
            'has_database': bool(cls.DATABASE_URL),
            'has_spotify_config': bool(cls.SPOTIFY_CLIENT_ID and cls.SPOTIFY_CLIENT_SECRET),
            'has_openai_config': bool(cls.OPENAI_API_KEY),
            'has_genius_config': bool(cls.GENIUS_ACCESS_TOKEN),
        }


class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Database settings for development
    DATABASE_POOL_SIZE = 5
    DATABASE_POOL_MIN = 2
    DATABASE_TIMEOUT = 30
    
    # Session settings for development
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_PATH = '/'
    
    # CORS settings for development
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    
    @classmethod
    def get_cors_origins(cls):
        """Get CORS origins including the frontend URL."""
        origins = cls.CORS_ORIGINS.copy()
        if cls.FRONTEND_URL:
            origins.append(cls.FRONTEND_URL)
        return origins


class ProductionConfig(Config):
    """Production configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Database settings for production
    DATABASE_POOL_SIZE = 10
    DATABASE_POOL_MIN = 3
    DATABASE_TIMEOUT = 60
    
    # Session settings for production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'None'  # For cross-origin requests
    SESSION_COOKIE_PATH = '/'
    
    # CORS settings for production
    CORS_ORIGINS = [
        "https://spotify-mood-player.vercel.app",
    ]
    
    @classmethod
    def get_cors_origins(cls):
        """Get CORS origins including the frontend URL."""
        origins = cls.CORS_ORIGINS.copy()
        if cls.FRONTEND_URL and cls.FRONTEND_URL not in origins:
            origins.append(cls.FRONTEND_URL)
        return origins


class ServerlessConfig(ProductionConfig):
    """Serverless (AWS Lambda) configuration."""
    
    # Database settings for serverless
    DATABASE_POOL_SIZE = 2
    DATABASE_POOL_MIN = 1
    DATABASE_TIMEOUT = 30
    
    # No SERVER_NAME for Lambda
    SERVER_NAME = None


def get_config():
    """Get the appropriate configuration based on environment."""
    env = os.getenv('FLASK_ENV', 'development')
    is_lambda = os.getenv('AWS_LAMBDA_FUNCTION_NAME') is not None
    
    if is_lambda:
        return ServerlessConfig
    elif env == 'production':
        return ProductionConfig
    else:
        return DevelopmentConfig


def log_config_info():
    """Log configuration information for debugging."""
    config = get_config()
    env_info = config.get_environment_info()
    
    logger.info("=== Configuration Info ===")
    logger.info(f"Environment: {os.getenv('FLASK_ENV', 'development')}")
    logger.info(f"Is Production: {env_info['is_production']}")
    logger.info(f"Is Lambda: {env_info['is_lambda']}")
    logger.info(f"Is Local Dev: {env_info['is_local_dev']}")
    logger.info(f"Has Database: {env_info['has_database']}")
    logger.info(f"Has Spotify Config: {env_info['has_spotify_config']}")
    logger.info(f"Has OpenAI Config: {env_info['has_openai_config']}")
    logger.info(f"Has Genius Config: {env_info['has_genius_config']}")
    logger.info(f"Database Pool Size: {config.DATABASE_POOL_SIZE}")
    logger.info(f"Database Pool Min: {config.DATABASE_POOL_MIN}")
    logger.info(f"Frontend URL: {config.FRONTEND_URL}")
    logger.info("=== End Configuration Info ===") 