"""
YAML configuration loader with environment variable override support.

Loads and merges multiple YAML configuration files, applies environment variable
overrides, and validates required fields for the intelligent sampling robotic arm system.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from .logger import get_logger

logger = get_logger(__name__)


class ConfigError(Exception):
    """Raised when configuration loading or validation fails."""

    pass


class ConfigLoader:
    """
    Loads, merges, and validates YAML configuration files.

    Supports nested environment variable overrides using the pattern:
    ENV_PATH__TO__KEY=value, where double underscores separate nested keys.
    """

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the config loader.

        Args:
            config_dir: Path to the configuration directory. Defaults to
                        'config/' relative to the project root.
        """
        if config_dir is None:
            config_dir = str(Path(__file__).resolve().parent.parent / "config")
        self.config_dir = Path(config_dir)
        self._config: Dict[str, Any] = {}
        self._loaded_files: List[str] = []

    def load(self, *filenames: str) -> Dict[str, Any]:
        """
        Load and merge one or more YAML configuration files.

        Files are loaded in order; later files override duplicate keys
        from earlier files.

        Args:
            *filenames: Names of YAML files to load (e.g., 'settings.yaml').

        Returns:
            Merged configuration dictionary.

        Raises:
            ConfigError: If a file cannot be read or parsed.
        """
        merged: Dict[str, Any] = {}

        for filename in filenames:
            filepath = self.config_dir / filename
            if not filepath.exists():
                raise ConfigError(f"Configuration file not found: {filepath}")

            logger.debug(f"Loading configuration from: {filepath}")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ConfigError(f"Failed to parse YAML file '{filepath}': {e}") from e
            except OSError as e:
                raise ConfigError(f"Failed to read file '{filepath}': {e}") from e

            if data is None:
                logger.warning(f"Empty configuration file: {filepath}")
                continue

            if not isinstance(data, dict):
                raise ConfigError(
                    f"Configuration file '{filepath}' must contain a mapping, "
                    f"got {type(data).__name__}"
                )

            merged = self._deep_merge(merged, data)
            self._loaded_files.append(str(filepath))

        self._config = merged
        logger.info(f"Loaded {len(self._loaded_files)} configuration file(s)")
        return self._config

    def load_all_defaults(self) -> Dict[str, Any]:
        """
        Load all default configuration files (settings.yaml, arm_params.yaml,
        sampling_params.yaml).

        Returns:
            Merged configuration dictionary.
        """
        return self.load("settings.yaml", "arm_params.yaml", "sampling_params.yaml")

    def apply_env_overrides(self, prefix: str = "RPI_") -> Dict[str, Any]:
        """
        Override configuration values from environment variables.

        Environment variables matching the pattern `{prefix}KEY__SUBKEY=value`
        override nested keys separated by double underscores in the loaded config.

        Args:
            prefix: Environment variable prefix to filter on.

        Returns:
            Updated configuration dictionary.
        """
        env_pattern = re.compile(rf"^{re.escape(prefix)}(.+)$")

        for env_key, env_value in os.environ.items():
            match = env_pattern.match(env_key)
            if not match:
                continue

            key_path = match.group(1).lower().split("__")
            self._set_nested(self._config, key_path, self._parse_env_value(env_value))
            logger.debug(f"Override from env: {env_key} -> {key_path}")

        return self._config

    def validate_required(
        self, required_paths: List[str]
    ) -> None:
        """
        Validate that required configuration paths exist.

        Args:
            required_paths: List of dot-separated paths (e.g., 'hardware.stm32.port').

        Raises:
            ConfigError: If a required path is missing.
        """
        for path in required_paths:
            keys = path.split(".")
            current = self._config
            traversed: List[str] = []

            for key in keys:
                if not isinstance(current, dict):
                    raise ConfigError(
                        f"Required config path '{path}' is invalid: "
                        f"'{'.'.join(traversed)}' is not a mapping"
                    )
                if key not in current:
                    raise ConfigError(
                        f"Required configuration key missing: '{path}'"
                    )
                current = current[key]
                traversed.append(key)

        logger.info(f"Validated {len(required_paths)} required config paths")

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated path.

        Args:
            path: Dot-separated key path (e.g., 'hardware.stm32.port').
            default: Default value if path is not found.

        Returns:
            The configuration value, or default.
        """
        keys = path.split(".")
        current = self._config

        for key in keys:
            if not isinstance(current, dict):
                return default
            if key not in current:
                return default
            current = current[key]

        return current

    @property
    def config(self) -> Dict[str, Any]:
        """Get the full merged configuration dictionary."""
        return self._config

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge two dictionaries. Override values take precedence.

        Args:
            base: Base dictionary.
            override: Override dictionary.

        Returns:
            Merged dictionary.
        """
        result = dict(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigLoader._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def _set_nested(
        data: Dict[str, Any], key_path: List[str], value: Any
    ) -> None:
        """
        Set a nested dictionary value from a key path.

        Args:
            data: Dictionary to modify.
            key_path: List of keys forming the path.
            value: Value to set.
        """
        current = data
        for key in key_path[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[key_path[-1]] = value

    @staticmethod
    def _parse_env_value(raw: str) -> Union[str, int, float, bool, None]:
        """
        Parse an environment variable string into its typed value.

        Args:
            raw: Raw string value from the environment.

        Returns:
            Parsed value with appropriate type.
        """
        lower = raw.lower()
        if lower in ("true", "yes", "1"):
            return True
        if lower in ("false", "no", "0"):
            return False
        if lower in ("none", "null", ""):
            return None
        try:
            return int(raw)
        except ValueError:
            pass
        try:
            return float(raw)
        except ValueError:
            pass
        return raw


# ------------------------------------------------------------------
# Convenience functions
# ------------------------------------------------------------------


def load_config(
    config_dir: Optional[str] = None,
    *filenames: str,
    apply_env: bool = True,
    env_prefix: str = "RPI_",
) -> ConfigLoader:
    """
    Convenience function to load configuration files and apply environment
    overrides.

    Args:
        config_dir: Path to config directory. Defaults to auto-detection.
        *filenames: Config filenames. Defaults to all three standard files.
        apply_env: Whether to apply environment variable overrides.
        env_prefix: Prefix for environment variable override detection.

    Returns:
        Configured ConfigLoader instance.
    """
    loader = ConfigLoader(config_dir)

    if not filenames:
        filenames = ("settings.yaml", "arm_params.yaml", "sampling_params.yaml")

    loader.load(*filenames)

    if apply_env:
        loader.apply_env_overrides(prefix=env_prefix)

    return loader