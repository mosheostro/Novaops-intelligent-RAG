"""ui/access.py — the Streamlit-only deployment boundary: Cloud secrets bridged
into os.environ for config.py, and the APP_PASSWORD gate. Pure helpers are
tested directly; the gate itself through AppTest. No AWS calls."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch

for _name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "BEDROCK_MODEL_ID",
              "BEDROCK_EMBEDDING_MODEL_ID", "OPENSEARCH_COLLECTION"):
    os.environ.setdefault(_name, "test-value")

from streamlit.testing.v1 import AppTest  # noqa: E402

from ui import access  # noqa: E402

APP = str(Path(__file__).resolve().parent.parent / "ui" / "app.py")


class BridgeSecretsTests(unittest.TestCase):
    def test_fills_missing_config_values_from_secrets(self):
        env = {}
        filled = access.bridge_secrets({"AWS_REGION": "us-east-1", "OPENSEARCH_ENDPOINT": "https://x"}, env)
        self.assertEqual(env, {"AWS_REGION": "us-east-1", "OPENSEARCH_ENDPOINT": "https://x"})
        self.assertEqual(sorted(filled), ["AWS_REGION", "OPENSEARCH_ENDPOINT"])  # names only, never values

    def test_never_overwrites_a_value_already_in_the_environment(self):
        env = {"AWS_REGION": "eu-west-1"}  # shell or .env value wins
        filled = access.bridge_secrets({"AWS_REGION": "us-east-1"}, env)
        self.assertEqual(env["AWS_REGION"], "eu-west-1")
        self.assertEqual(filled, [])

    def test_blank_environment_value_counts_as_missing_like_config_py(self):
        env = {"AWS_REGION": "  "}  # `cp .env.example .env` leaves values blank
        access.bridge_secrets({"AWS_REGION": "us-east-1"}, env)
        self.assertEqual(env["AWS_REGION"], "us-east-1")

    def test_covers_exactly_config_py_contract_and_never_bridges_the_app_password(self):
        import config
        self.assertEqual(set(access.CONFIG_KEYS),
                         set(config.REQUIRED) | set(config.OPENSEARCH_CREDENTIAL_PAIR) | {"OPENSEARCH_ENDPOINT"})
        env = {}
        access.bridge_secrets({"APP_PASSWORD": "pw", "UNRELATED": "x"}, env)
        self.assertEqual(env, {})  # the UI password stays out of the environment the RAG code reads

    def test_blank_or_non_string_secrets_are_ignored(self):
        env = {}
        access.bridge_secrets({"AWS_REGION": " ", "BEDROCK_MODEL_ID": {"nested": "table"}}, env)
        self.assertEqual(env, {})

    def test_read_secrets_is_empty_when_no_secrets_file_exists_locally(self):
        class _Missing:
            def to_dict(self):
                raise FileNotFoundError("no secrets.toml")  # StreamlitSecretNotFoundError subclasses this
        with patch.object(access.st, "secrets", _Missing()):
            self.assertEqual(access.read_secrets(), {})


class PasswordTests(unittest.TestCase):
    def test_configured_password_prefers_environment_then_secrets(self):
        self.assertEqual(access.configured_password({"APP_PASSWORD": "cloud"}, {"APP_PASSWORD": "local"}), "local")
        self.assertEqual(access.configured_password({"APP_PASSWORD": "cloud"}, {}), "cloud")

    def test_missing_empty_or_whitespace_password_is_not_configured(self):
        for secrets, env in (({}, {}), ({"APP_PASSWORD": ""}, {}), ({}, {"APP_PASSWORD": "   "}),
                             ({"APP_PASSWORD": " \t"}, {"APP_PASSWORD": ""})):
            with self.subTest(secrets=secrets, env=env):
                self.assertIsNone(access.configured_password(secrets, env))

    def test_matching_uses_constant_time_comparison(self):
        with patch.object(access.hmac, "compare_digest", wraps=access.hmac.compare_digest) as spy:
            self.assertTrue(access.password_matches("s3cret", "s3cret"))
            self.assertFalse(access.password_matches("s3cre", "s3cret"))
            self.assertFalse(access.password_matches("", "s3cret"))
        self.assertEqual(spy.call_count, 3)


class _GateTestCase(unittest.TestCase):
    """A dashboard with APP_PASSWORD configured, the developer's .env and
    secrets kept out, and ask.ask mocked."""

    def setUp(self):
        self.env = patch.dict(os.environ, {"APP_PASSWORD": "correct horse"})
        self.env.start()
        self.addCleanup(self.env.stop)
        patch("ui.access.load_local_env").start()  # never read the developer's real .env in tests
        patch("ui.access.read_secrets", return_value={}).start()
        self.ask = patch("ask.ask").start()
        patch("ui.state.opensearch_client", return_value=object()).start()  # never a real connection
        self.addCleanup(patch.stopall)

    def _app(self):
        return AppTest.from_file(APP, default_timeout=30).run()

    def _sign_in(self, at, password):
        at.text_input(key="login_password").input(password)
        at.button[0].click().run()  # the form's "Sign in" submit button
        return at



class GateTests(_GateTestCase):
    """The whole UI is behind the gate; nothing of the RAG app renders first."""

    def test_login_screen_is_shown_and_nothing_else_renders(self):
        at = self._app()
        self.assertFalse(at.exception)
        self.assertEqual([t.value for t in at.title], ["NovaOps Intelligent RAG"])
        self.assertEqual(len(at.chat_input), 0)          # no Chat page
        self.assertEqual(len(at.sidebar.radio), 0)       # no role selector / navigation
        self.assertFalse(at.session_state["authenticated"] if "authenticated" in at.session_state else False)

    def test_correct_password_authenticates_and_renders_the_dashboard(self):
        at = self._sign_in(self._app(), "correct horse")
        self.assertFalse(at.exception)
        self.assertTrue(at.session_state["authenticated"])
        self.assertIn("Ask NovaOps", [t.value for t in at.title])

    def test_wrong_password_is_rejected_with_a_concise_error(self):
        at = self._sign_in(self._app(), "wrong")
        self.assertFalse(at.session_state["authenticated"] if "authenticated" in at.session_state else False)
        errors = [e.value for e in at.error]
        self.assertEqual(errors, ["Incorrect password."])
        self.assertNotIn("correct horse", "\n".join(errors))
        self.assertNotIn("Ask NovaOps", [t.value for t in at.title])

    def test_missing_or_blank_password_fails_closed_with_a_configuration_error(self):
        for value in (None, "", "   "):
            with self.subTest(value=value):
                if value is None:
                    os.environ.pop("APP_PASSWORD", None)
                else:
                    os.environ["APP_PASSWORD"] = value
                at = self._app()
                self.assertFalse(at.exception)
                self.assertEqual(len(at.text_input), 0)   # no login form, no passwordless mode
                self.assertEqual(len(at.chat_input), 0)
                self.assertIn("APP_PASSWORD", at.error[0].value)

    def test_session_state_keeps_the_user_signed_in(self):
        at = self._sign_in(self._app(), "correct horse")
        at.run()
        self.assertIn("Ask NovaOps", [t.value for t in at.title])


class PageStructureTests(unittest.TestCase):
    """Root cause of the E2E bypass: a `pages/` folder next to the entry script
    turns on Streamlit's legacy auto-discovered pages. The login run stops before
    st.navigation, so Streamlit fell back to them and executed a page file on its
    own — no gate, no config, no sidebar (the missing `role` and Help). Page
    scripts must therefore live somewhere Streamlit never auto-discovers."""

    UI = Path(APP).parent

    def test_no_legacy_pages_directory_next_to_the_entry_script(self):
        self.assertFalse((self.UI / "pages").exists())

    def test_every_page_and_page_link_points_at_an_existing_app_pages_script(self):
        import re
        sources = [p for p in self.UI.rglob("*.py")]
        paths = {m for p in sources for m in re.findall(r"""["'](app_pages/[\w_]+\.py)["']""",
                                                         p.read_text(encoding="utf-8"))}
        self.assertTrue(paths)
        for rel in paths:
            with self.subTest(page=rel):
                self.assertTrue((self.UI / rel).is_file())
        self.assertFalse(any(re.search(r"""["']pages/""", p.read_text(encoding="utf-8")) for p in sources))


class AuthenticatedLifecycleTests(_GateTestCase):
    """After a REAL sign-in (not a pre-set session flag): shared sidebar first,
    then navigation and pages."""

    def test_sign_in_renders_role_and_help_before_chat_needs_the_role(self):
        from test_ui_smoke import ASK_RESULT
        self.ask.return_value = ASK_RESULT
        at = self._sign_in(self._app(), "correct horse")
        self.assertEqual([r.key for r in at.sidebar.radio], ["role"])
        self.assertEqual(at.session_state["role"], "employee")
        self.assertIn("Help", [e.label for e in at.sidebar.expander])
        at.chat_input[0].set_value("How does PTO accrue?").run()
        self.assertFalse(at.exception)
        self.assertEqual(self.ask.call_args.args[2], "employee")

    def test_role_choice_survives_and_reaches_chat(self):
        from test_ui_smoke import ASK_RESULT
        self.ask.return_value = ASK_RESULT
        at = self._sign_in(self._app(), "correct horse")
        at.sidebar.radio(key="role").set_value("manager").run()
        at.chat_input[0].set_value("q").run()
        self.assertEqual(self.ask.call_args.args[2], "manager")


class ConfigurationErrorTests(unittest.TestCase):
    """An incomplete backend configuration after sign-in is a clear, safe
    configuration error — no traceback, no values."""

    def setUp(self):
        import sys
        patch.dict(os.environ, {"APP_PASSWORD": "pw", "AWS_SECRET_ACCESS_KEY": "SECRET-VALUE-XYZ"}).start()
        os.environ.pop("OPENSEARCH_COLLECTION", None)
        patch.dict(sys.modules).start()
        sys.modules.pop("config", None)                  # force app.py's `import config` to validate afresh
        patch("dotenv.load_dotenv").start()              # never read the developer's real .env
        patch("ui.access.load_local_env").start()
        patch("ui.access.read_secrets", return_value={}).start()
        self.addCleanup(patch.stopall)

    def test_missing_backend_variable_shows_a_configuration_error_without_details_leaking(self):
        at = AppTest.from_file(APP, default_timeout=30)
        at.session_state["authenticated"] = True
        at.run()
        self.assertFalse(at.exception)                   # no raw traceback in the UI
        text = "\n".join(e.value for e in at.error)
        self.assertIn("Configuration error", text)
        self.assertIn("OPENSEARCH_COLLECTION", text)     # the missing NAME, which is not a secret
        self.assertNotIn("SECRET-VALUE-XYZ", text)
        self.assertEqual(len(at.chat_input), 0)


class CliDoesNotNeedThePasswordTests(unittest.TestCase):
    def test_eval_and_the_rag_modules_never_read_app_password(self):
        root = Path(__file__).resolve().parent.parent
        for name in ("config.py", "client.py", "retrieval.py", "planner.py", "reranker.py", "judges.py",
                     "eval.py", "ask.py", "runs.py", "models.py"):
            with self.subTest(module=name):
                self.assertNotIn("APP_PASSWORD", (root / name).read_text(encoding="utf-8"))

    def test_config_imports_without_app_password(self):
        import importlib
        import config
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("APP_PASSWORD", None)
            importlib.reload(config)  # validates the six required variables only


if __name__ == "__main__":
    unittest.main()
