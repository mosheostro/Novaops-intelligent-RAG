"""The saved-runs table and its row selection.

Streamlit keeps a dataframe's selection as row INDICES in widget state across
reruns. The run list changes under it — a run deleted, or a new run finished
(the list is newest first, so every row shifts) — and a kept index would then
crash (IndexError) or silently point at a different run. So the widget key is
derived from the current run ids: any change to the list is a fresh widget with
no selection, and a stale index is ignored as a second line of defence.
"""
import hashlib

import pandas as pd
import streamlit as st

import runs


def table_key(listed: list[runs.RunInfo]) -> str:
    digest = hashlib.sha1("|".join(r.id for r in listed).encode("utf-8")).hexdigest()[:12]
    return f"runs_table::{digest}"


def selected_run(listed: list[runs.RunInfo], rows: list[int]) -> runs.RunInfo | None:
    if rows and 0 <= rows[0] < len(listed):
        return listed[rows[0]]
    return None


def render(listed: list[runs.RunInfo]) -> runs.RunInfo | None:
    df = pd.DataFrame([{
        "Run": r.id,
        "Started (UTC)": r.started.strftime("%Y-%m-%d %H:%M") if r.started else "—",
        "Questions": ", ".join(r.question_ids) if r.question_ids is not None else "—",
        "Configurations": len(r.configs) if r.configs is not None else None,
        "Cutoff": r.cutoff.isoformat() if r.cutoff else "—",
        "Status": r.status,
    } for r in listed])
    event = st.dataframe(df, hide_index=True, key=table_key(listed), on_select="rerun",
                         selection_mode="single-row")
    return selected_run(listed, event.selection.rows)
