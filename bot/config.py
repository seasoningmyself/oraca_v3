"""
Configuration management for the Discord bot.
Loads settings from config.yaml and environment variables.
"""
import os
import yaml
from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class ChannelConfig(BaseModel):
    """Discord channel configuration"""
    general: int
    alerts: int
    logs: int
    errors: int


class DiscordConfig(BaseModel):
    """Discord-specific configuration"""
    token_env: str
    channels: ChannelConfig


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AppConfig(BaseModel):
    """Application-level configuration"""
    name: str = "Oraca Trading Bot"
    environment: str = "development"


class Config(BaseModel):
    """Main configuration container"""
    discord: DiscordConfig
    logging: LoggingConfig
    app: AppConfig

    @property
    def discord_token(self) -> str:
        """Get Discord token from environment variable"""
        token = os.getenv(self.discord.token_env)
        if not token:
            raise ValueError(
                f"Discord token not found in environment variable: {self.discord.token_env}"
            )
        return token

    def get_channel_id(self, channel_name: str) -> int:
        """Get channel ID by name"""
        if not hasattr(self.discord.channels, channel_name):
            raise ValueError(f"Channel '{channel_name}' not found in configuration")
        return getattr(self.discord.channels, channel_name)


def load_config(
    config_path: str = None,
    env_file: str = None,
    search_parent_dirs: bool = True
) -> Config:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config.yaml file. If None, searches for config.yaml
                    starting from bot/ directory, optionally checking parent dirs.
        env_file: Path to .env file. If None, searches for .env.local in current
                 and parent directories.
        search_parent_dirs: If True, searches parent directories for .env and config files.
                           Useful when bot is used as a sub-package.

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
        config_path = os.getenv('BOT_CONFIG_PATH')

        if config_path is None:
            # Default: look in bot/ directory
            bot_dir = Path(__file__).parent
            config_path = bot_dir / "config.yaml"

            # If not found and search_parent_dirs is True, check parent
            if not Path(config_path).exists() and search_parent_dirs:
                # Check if there's a config in project root
                project_root = bot_dir.parent
                alt_config = project_root / "config" / "bot.yaml"
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
