"""Process-wide resources shared by the UI pages."""
import streamlit as st

from client import opensearch_client


@st.cache_resource
def get_client():
    return opensearch_client()
