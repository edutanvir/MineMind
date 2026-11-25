"""Saved questions in Cloud Firestore (optional feature, off unless MINEMIND_ENABLE_ACCOUNTS=1).

No Streamlit imports here. The Firestore client is created lazily, so local runs and
the public demo need no Google Cloud setup. Tests inject a fake client.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

MAX_QUESTION_CHARS = 1000
MAX_ANSWER_CHARS = 8000
_client = None


def enabled() -> bool:
    return os.getenv("MINEMIND_ENABLE_ACCOUNTS") == "1"


def _get_client():
    global _client
    if _client is None:
        from google.cloud import firestore  # lazy import

        _client = firestore.Client(project=os.getenv("GOOGLE_CLOUD_PROJECT") or None)
    return _client


def _history(email: str, client=None):
    c = client or _get_client()
    return c.collection("users").document(email.strip().lower()).collection("history")


def save_question(email: str, question: str, answer: str, tool_calls: list, client=None) -> str:
    """Store one question and answer. Only tool names are kept, never tool arguments or keys."""
    doc = {
        "question": question[:MAX_QUESTION_CHARS],
        "answer": answer[:MAX_ANSWER_CHARS],
        "tools": [c["tool"] for c in tool_calls],
        "created_at": datetime.now(timezone.utc),
    }
    _, ref = _history(email, client).add(doc)
    return ref.id


def list_questions(email: str, limit: int = 20, client=None) -> list[dict]:
    """Newest first."""
    query = _history(email, client).order_by("created_at", direction="DESCENDING").limit(limit)
    return [{"id": d.id, **d.to_dict()} for d in query.stream()]


def delete_question(email: str, doc_id: str, client=None) -> None:
    _history(email, client).document(doc_id).delete()


def delete_all(email: str, client=None) -> int:
    """Delete every saved question for this user. Returns how many were removed."""
    removed = 0
    for snapshot in _history(email, client).stream():
        snapshot.reference.delete()
        removed += 1
    return removed
