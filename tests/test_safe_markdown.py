"""neutralize_links — Option A: every link in model/user text shown through
st.markdown becomes non-clickable text; other Markdown is left alone."""
import re
import unittest

from ui.components.safe_markdown import neutralize_links

# Anything Streamlit's Markdown would turn into a link: an inline/image/reference
# link, an angle-bracket autolink, or a bare URL / www. / e-mail outside a code span.
_LINK_SYNTAX = re.compile(r"\]\(|\]\[|<[a-z][a-z0-9+.-]*:|^\s*\[[^\]]+\]:\s", re.I | re.M)


def _outside_code(text: str) -> str:
    return re.sub(r"```.*?```|`[^`]*`", "", text, flags=re.S)


def _assert_nothing_clickable(case: unittest.TestCase, text: str) -> None:
    case.assertIsNone(_LINK_SYNTAX.search(text), text)
    bare = re.search(r"(?:https?|ftp|file)://|\bwww\.|\S+@\S+\.\w+", _outside_code(text))
    case.assertIsNone(bare, text)


class NeutralizeLinksTests(unittest.TestCase):
    def test_the_reported_relative_md_link_keeps_its_label_and_loses_its_target(self):
        out = neutralize_links("Additional unpaid leave may be available; see [state and family leave](stateFMLA.md).")
        self.assertEqual(out, "Additional unpaid leave may be available; see state and family leave.")
        self.assertNotIn("stateFMLA.md", out)
        _assert_nothing_clickable(self, out)

    def test_every_inline_link_target_kind_becomes_its_label(self):
        for target in ("stateFMLA.md", "../handbook/benefits.md", "docs/x.md#pto", "#anchor",
                       "http://localhost:8501/stateFMLA.md", "http://127.0.0.1:8501/x", "file:///C:/data/x.md",
                       "https://bamboohr.novaops.example/time-off", "https://www.example.com/page",
                       'https://example.com "with a title"', "mailto:hr@novaops.example"):
            with self.subTest(target=target):
                out = neutralize_links(f"See [the policy]({target}) now.")
                self.assertEqual(out, "See the policy now.")
                _assert_nothing_clickable(self, out)

    def test_reference_style_links_and_their_definitions_are_neutralized(self):
        out = neutralize_links("Read [the guide][g] and [this][].\n\n[g]: https://wiki.novaops.example/guide\n"
                               "[this]: stateFMLA.md \"State leave\"")
        self.assertEqual(out.strip(), "Read the guide and this.")
        _assert_nothing_clickable(self, out)

    def test_images_become_alt_text_and_load_nothing(self):
        out = neutralize_links("Chart: ![org chart](https://cdn.example.com/org.png) and ![](local/diagram.png)")
        self.assertEqual(out, "Chart: org chart and ")
        _assert_nothing_clickable(self, out)

    def test_angle_bracket_autolinks_become_non_clickable_code_text(self):
        out = neutralize_links("Portal: <https://it.novaops.example/help> or <mailto:it@novaops.example>.")
        self.assertEqual(out, "Portal: `https://it.novaops.example/help` or `mailto:it@novaops.example`.")
        _assert_nothing_clickable(self, out)

    def test_bare_urls_www_and_emails_become_non_clickable_code_text(self):
        out = neutralize_links("Open http://localhost:8501/stateFMLA.md, www.example.com or "
                               "https://status.novaops.example/ (status). Mail hr@novaops.example.")
        self.assertEqual(out, "Open `http://localhost:8501/stateFMLA.md`, `www.example.com` or "
                              "`https://status.novaops.example/` (status). Mail `hr@novaops.example`.")
        _assert_nothing_clickable(self, out)

    def test_a_link_whose_label_is_itself_a_url_ends_up_non_clickable(self):
        out = neutralize_links("[https://bamboohr.novaops.example](https://bamboohr.novaops.example)")
        self.assertEqual(out, "`https://bamboohr.novaops.example`")
        _assert_nothing_clickable(self, out)

    def test_ordinary_markdown_formatting_is_preserved(self):
        text = ("## Parental leave\n\n**Primary caregivers** get *16 weeks*:\n\n"
                "1. Paid at 100%\n2. Within the first year\n\n- item\n\n> quoted\n\n| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertEqual(neutralize_links(text), text)

    def test_existing_code_is_left_untouched(self):
        text = "Run `curl https://api.example.com` or:\n\n```\nsee [x](y.md) at https://example.com\n```\nDone."
        self.assertEqual(neutralize_links(text), text)

    def test_plain_text_mentions_of_files_are_not_changed(self):
        self.assertEqual(neutralize_links("The stateFMLA.md document covers leave."),
                         "The stateFMLA.md document covers leave.")

    def test_empty_text(self):
        self.assertEqual(neutralize_links(""), "")


if __name__ == "__main__":
    unittest.main()
