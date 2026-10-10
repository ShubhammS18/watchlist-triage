"""Which providers exist, and the configuration file that picks one.

Changing the model means changing the JSON file and nothing else. The file holds no secrets.
"""
import json
from pathlib import Path

from . import Settings
from .stub import Stub

DEFAULT_CONFIG = Path(__file__).with_name("config.json")

# Provider name -> a function that takes that provider's options and returns a model.
# A real adapter is added here. Task T04 ships none, so there is no SDK and no key.
PROVIDERS = {"stub": Stub}

REQUIRED = ("provider", "model", "temperature", "max_tokens", "timeout_s")
OPTIONAL = ("options",)


class ConfigError(ValueError):
    """The configuration file is missing, unreadable or wrong. Nothing should start."""


def load(path=DEFAULT_CONFIG):
    """Read the configuration and return (model, settings)."""
    try:
        config = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"cannot read configuration {str(path)!r}: {error}") from error
    if not isinstance(config, dict):
        raise ConfigError("the configuration must be a JSON object")
    missing = [key for key in REQUIRED if key not in config]
    unknown = sorted(set(config) - set(REQUIRED) - set(OPTIONAL))
    if missing or unknown:
        raise ConfigError(f"configuration keys are wrong: missing {missing}, unknown {unknown}")
    if not isinstance(config["provider"], str) or config["provider"] not in PROVIDERS:
        raise ConfigError(f"unknown provider {config['provider']!r}; known providers: {sorted(PROVIDERS)}")
    options = config.get("options", {})
    if not isinstance(options, dict):
        raise ConfigError("options must be a JSON object")
    try:
        settings = Settings(*(config[key] for key in REQUIRED[1:]))
        model = PROVIDERS[config["provider"]](**options)
    except (TypeError, ValueError) as error:
        raise ConfigError(f"configuration is invalid: {error}") from error
    return model, settings
