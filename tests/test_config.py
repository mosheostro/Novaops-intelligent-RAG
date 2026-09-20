"""Deterministic tests for config.py — no network, no AWS, no real credentials."""
import os
import unittest

# config validates the environment at import time. Dummy values set BEFORE the import
# take precedence over any real .env (load_dotenv does not override existing variables).
for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

import config  # noqa: E402

VALID = {
    "AWS_ACCESS_KEY_ID": "id",
    "AWS_SECRET_ACCESS_KEY": "secret",
    "AWS_REGION": "us-east-1",
    "BEDROCK_MODEL_ID": "chat-model",
    "BEDROCK_EMBEDDING_MODEL_ID": "embed-model",
    "OPENSEARCH_COLLECTION": "my-collection",
}


class LoadConfigTests(unittest.TestCase):
    def test_valid_env_returns_non_secret_settings(self):
        cfg = config.load_config(VALID)
        self.assertEqual(cfg["AWS_REGION"], "us-east-1")
        self.assertEqual(cfg["BEDROCK_MODEL_ID"], "chat-model")
        self.assertEqual(cfg["BEDROCK_EMBEDDING_MODEL_ID"], "embed-model")
        self.assertEqual(cfg["OPENSEARCH_COLLECTION"], "my-collection")
        self.assertIsNone(cfg["OPENSEARCH_ENDPOINT"])

    def test_credentials_are_required_but_never_exposed(self):
        cfg = config.load_config(VALID)
        self.assertNotIn("AWS_ACCESS_KEY_ID", cfg)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", cfg)

    def test_all_missing_variables_reported_together(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config({})
        message = str(ctx.exception)
        for name in VALID:
            self.assertIn(name, message)

    def test_only_the_missing_ones_are_named(self):
        env = {k: v for k, v in VALID.items() if k not in ("AWS_REGION", "BEDROCK_MODEL_ID")}
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config(env)
        message = str(ctx.exception)
        self.assertIn("AWS_REGION", message)
        self.assertIn("BEDROCK_MODEL_ID", message)
        self.assertNotIn("OPENSEARCH_COLLECTION", message)

    def test_blank_value_counts_as_missing(self):
        # `cp .env.example .env` leaves every value blank — that must fail, not pass.
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config({**VALID, "AWS_REGION": "   "})
        self.assertIn("AWS_REGION", str(ctx.exception))

    def test_no_default_for_region_or_model_ids(self):
        for name in ("AWS_REGION", "BEDROCK_MODEL_ID", "BEDROCK_EMBEDDING_MODEL_ID"):
            env = {k: v for k, v in VALID.items() if k != name}
            with self.assertRaises(config.ConfigError, msg=name):
                config.load_config(env)

    def test_optional_endpoint_is_exposed_when_set(self):
        cfg = config.load_config({**VALID, "OPENSEARCH_ENDPOINT": "https://example.invalid"})
        self.assertEqual(cfg["OPENSEARCH_ENDPOINT"], "https://example.invalid")


class OpenSearchCredentialPairTests(unittest.TestCase):
    def test_neither_is_valid(self):
        config.load_config(VALID)

    def test_both_is_valid(self):
        config.load_config({**VALID, "OPENSEARCH_AWS_ACCESS_KEY_ID": "a",
                            "OPENSEARCH_AWS_SECRET_ACCESS_KEY": "b"})

    def test_only_key_id_is_rejected(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config({**VALID, "OPENSEARCH_AWS_ACCESS_KEY_ID": "a"})
        self.assertIn("OPENSEARCH_AWS_SECRET_ACCESS_KEY", str(ctx.exception))

    def test_only_secret_is_rejected(self):
        with self.assertRaises(config.ConfigError) as ctx:
            config.load_config({**VALID, "OPENSEARCH_AWS_SECRET_ACCESS_KEY": "b"})
        self.assertIn("OPENSEARCH_AWS_ACCESS_KEY_ID", str(ctx.exception))

    def test_blank_half_counts_as_unset(self):
        config.load_config({**VALID, "OPENSEARCH_AWS_ACCESS_KEY_ID": "",
                            "OPENSEARCH_AWS_SECRET_ACCESS_KEY": ""})


class ModuleContractTests(unittest.TestCase):
    def test_module_exposes_validated_constants(self):
        for name in ("AWS_REGION", "BEDROCK_MODEL_ID", "BEDROCK_EMBEDDING_MODEL_ID",
                     "OPENSEARCH_COLLECTION", "OPENSEARCH_ENDPOINT"):
            self.assertTrue(hasattr(config, name), name)


if __name__ == "__main__":
    unittest.main()
