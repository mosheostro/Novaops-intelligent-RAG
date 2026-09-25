"""Central configuration: load `.env`, validate it, expose the non-secret settings.

Import this FIRST in every entry point. It validates at import time (no network, no
client construction), so a missing variable stops the run with one clear message
before anything else reads the environment. Region and model IDs have no defaults.

client.py, judges.py and subjects.py read the environment themselves and are not
routed through this module; it is the contract for the application modules.
"""
import logging
import os
from collections.abc import Mapping

from dotenv import find_dotenv, load_dotenv

logger = logging.getLogger(__name__)

load_dotenv(find_dotenv())

REQUIRED = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION",
    "BEDROCK_MODEL_ID",
    "BEDROCK_EMBEDDING_MODEL_ID",
    "OPENSEARCH_COLLECTION",
)
# Optional pair: client.py signs OpenSearch calls with these instead of the AWS_* keys.
OPENSEARCH_CREDENTIAL_PAIR = ("OPENSEARCH_AWS_ACCESS_KEY_ID", "OPENSEARCH_AWS_SECRET_ACCESS_KEY")


class ConfigError(RuntimeError):
    """The environment is missing or inconsistent. The message names every problem."""


def _value(env: Mapping[str, str], name: str) -> str:
    # A blank value counts as unset: `cp .env.example .env` leaves every value empty.
    return (env.get(name) or "").strip()


def load_config(env: Mapping[str, str]) -> dict:
    """Validate `env` and return the non-secret settings. Raises ConfigError listing
    every missing variable at once. Credentials are required but deliberately not
    returned: boto3 and client.py read them from the environment themselves."""
    missing = [name for name in REQUIRED if not _value(env, name)]
    if missing:
        logger.error("missing required environment variables: %s", ", ".join(missing))
        raise ConfigError(
            "Missing required environment variables: " + ", ".join(missing)
            + ". Set them in .env (see .env.example) or the shell."
        )
    key_id, secret = (_value(env, name) for name in OPENSEARCH_CREDENTIAL_PAIR)
    if bool(key_id) != bool(secret):
        unset = OPENSEARCH_CREDENTIAL_PAIR[1] if key_id else OPENSEARCH_CREDENTIAL_PAIR[0]
        logger.error("incomplete OpenSearch credential pair: %s is missing", unset)
        raise ConfigError(f"Set both OpenSearch credentials or neither: {unset} is missing.")
    return {
        "AWS_REGION": _value(env, "AWS_REGION"),
        "BEDROCK_MODEL_ID": _value(env, "BEDROCK_MODEL_ID"),
        "BEDROCK_EMBEDDING_MODEL_ID": _value(env, "BEDROCK_EMBEDDING_MODEL_ID"),
        "OPENSEARCH_COLLECTION": _value(env, "OPENSEARCH_COLLECTION"),
        "OPENSEARCH_ENDPOINT": _value(env, "OPENSEARCH_ENDPOINT") or None,
    }


_settings = load_config(os.environ)
AWS_REGION = _settings["AWS_REGION"]
BEDROCK_MODEL_ID = _settings["BEDROCK_MODEL_ID"]
BEDROCK_EMBEDDING_MODEL_ID = _settings["BEDROCK_EMBEDDING_MODEL_ID"]
OPENSEARCH_COLLECTION = _settings["OPENSEARCH_COLLECTION"]
OPENSEARCH_ENDPOINT = _settings["OPENSEARCH_ENDPOINT"]  # None unless pinned in .env
