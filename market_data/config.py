"""
Configuration management for the Market Data module.
Loads settings from config.yaml and environment variables.
"""
import os
import yaml
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv


class MassiveConfig(BaseModel):
    """Massive API configuration"""
    api_key_env: str
    base_url: str = "https://api.massive.com"


class DatabaseConfig(BaseModel):
    """Database configuration"""
    host: str
    port: int
    database: str
    user: Optional[str] = None  # Direct user (for dev)
    password: Optional[str] = None  # Direct password (for dev)
    user_env: Optional[str] = None  # Or environment variable name
    password_env: Optional[str] = None  # Or environment variable name
    min_pool_size: int = 5
    max_pool_size: int = 20


class TickersConfig(BaseModel):
    """Tickers configuration"""
    watch_list: List[str]


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AppConfig(BaseModel):
    """Application-level configuration"""
    name: str = "Oraca Market Data"
    environment: str = "development"


class Config(BaseModel):
    """Main configuration container"""
    massive: MassiveConfig
    database: DatabaseConfig
    tickers: TickersConfig
    timeframes: List[str]
    logging: LoggingConfig
    app: AppConfig

    @property
    def massive_api_key(self) -> str:
        """Get Massive API key from environment variable"""
        api_key = os.getenv(self.massive.api_key_env)
        if not api_key:
            raise ValueError(
                f"Massive API key not found in environment variable: {self.massive.api_key_env}"
            )
        return api_key

    @property
    def db_user(self) -> str:
        """Get database user (from direct config or environment variable)"""
        # Try direct config first
        if self.database.user:
            return self.database.user

        # Fall back to environment variable
        if self.database.user_env:
            user = os.getenv(self.database.user_env)
            if user:
                return user

        # Default to postgres for dev
        return "postgres"

    @property
    def db_password(self) -> str:
        """Get database password (from direct config or environment variable)"""
        # Try direct config first
        if self.database.password is not None:
            return self.database.password

        # Fall back to environment variable
        if self.database.password_env:
            password = os.getenv(self.database.password_env)
            if password:
                return password

        # Default to empty for dev (trust authentication)
        return ""

    @property
    def db_dsn(self) -> str:
        """Get database DSN (connection string)"""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.database.host}:{self.database.port}/{self.database.database}"


def load_config(
    config_path: str = None,
    env_file: str = None,
    search_parent_dirs: bool = True
) -> Config:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config.yaml file. If None, looks in market_data/ directory.
        env_file: Path to .env file. If None, searches for .env.local in current
                 and parent directories.
        search_parent_dirs: If True, searches parent directories for .env and config files.

    Returns:
        Config: Validated configuration object
    """
    # Load environment variables
    if env_file is None:
        # Try to find .env.local in current or parent directories
        current_dir = Path.cwd()
        for parent in [current_dir] + list(current_dir.parents):
            env_path = parent / '.env.local'
            if env_path.exists():
                load_dotenv(env_path)
                break
        else:
            # Fallback: try current directory
            load_dotenv('.env.local')
    else:
        load_dotenv(env_file)

    # Determine config file path
    if config_path is None:
        # Check if environment variable is set
        config_path = os.getenv('MARKET_DATA_CONFIG_PATH')

        if config_path is None:
            # Default: look in market_data/ directory
            module_dir = Path(__file__).parent
            config_path = module_dir / "config.yaml"

            # If not found and search_parent_dirs is True, check parent
            if not Path(config_path).exists() and search_parent_dirs:
                # Check if there's a config in project root
                project_root = module_dir.parent
                alt_config = project_root / "config" / "market_data.yaml"
                if alt_config.exists():
                    config_path = alt_config

    # Load YAML configuration
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)

    # Validate and create config object
    return Config(**config_data)


# Global config instance
_config: Config = None


def get_config(
    config_path: str = None,
    env_file: str = None,
    reload: bool = False
) -> Config:
    """
    Get the global configuration instance.

    Args:
        config_path: Optional path to config file (only used on first load or reload)
        env_file: Optional path to .env file (only used on first load or reload)
        reload: If True, reload configuration from disk

    Returns:
        Config: Configuration instance
    """
    global _config
    if _config is None or reload:
        _config = load_config(config_path=config_path, env_file=env_file)
    return _config


def set_config(config: Config) -> None:
    """
    Manually set the global configuration instance.
    Useful for testing or programmatic configuration.

    Args:
        config: Configuration object to use
    """
    global _config
    _config = config


def reset_config() -> None:
    """Reset the global configuration instance. Useful for testing."""
    global _config
    _config = None
