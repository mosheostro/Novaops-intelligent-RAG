"""Judge scores with their one-line reasons, plus what was expected and which
judges ran. The evaluation type already encodes the case: RefusalEvaluation =
expected refusal (only the refusal judge ran), ContentEvaluation = expected
answer (only the content judges ran), LiveJudgement = custom Chat question
(no expectation, so the refusal judge's verdict is shown as detected behavior
only — never as Refusal OK). Nothing here computes a score."""
import streamlit as st

from models import ContentEvaluation, LiveJudgement, RefusalEvaluation


def _score(label: str, score: float, reason: str) -> None:
    st.progress(min(max(score, 0.0), 1.0), text=f"**{label}** {score:.2f}")
    st.caption(reason)


def _not_run(label: str, why: str) -> None:
    st.markdown(f"**{label}** :gray[n/a]")
    st.caption(why)


def render(evaluation: ContentEvaluation | RefusalEvaluation | LiveJudgement) -> None:
    if isinstance(evaluation, RefusalEvaluation):
        actual = (":green-badge[:material/block: refused]" if evaluation.refusal_ok
                  else ":red-badge[:material/chat: did not refuse]")
        verdict = ":green-badge[Refusal OK ✓]" if evaluation.refusal_ok else ":red-badge[Refusal OK ✗]"
        st.markdown(f"Expected: refusal · Actual (refusal judge): {actual} · {verdict}")
        st.caption("Refusal case: content judges skipped (faithfulness, context relevance, completeness).")
        return

    if isinstance(evaluation, ContentEvaluation):
        st.markdown("Expected: answer · :gray-badge[Refusal: not judged — answerable case]")
    else:
        detected = (":orange-badge[:material/block: Refusal: Yes]" if evaluation.refused
                    else ":blue-badge[Refusal: No]")
        st.markdown(f"Expected: none — custom question · Detected (refusal judge): {detected}")
    cols = st.columns(3)
    with cols[0]:
        _score("Faithfulness", evaluation.faithfulness, evaluation.faithfulness_reason)
    with cols[1]:
        _score("Context relevance", evaluation.context_relevance, evaluation.context_relevance_reason)
    with cols[2]:
        if isinstance(evaluation, ContentEvaluation):
            _score("Completeness", evaluation.completeness, evaluation.completeness_reason)
        elif evaluation.completeness is not None:
            # a different metric from batch completeness (context, not key facts) — labelled apart
            _score("Completeness (vs. retrieved context)", evaluation.completeness, evaluation.completeness_reason)
        else:
            _not_run("Completeness (vs. retrieved context)",
                     "n/a — no usable context (no selected chunks, or the answer is a refusal).")
