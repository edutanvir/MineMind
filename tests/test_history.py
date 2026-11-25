"""Tests for saved questions (fake Firestore client) and the retry/fallback logic."""
from datetime import datetime, timedelta, timezone

import pytest

from src.cloud import history


# ---- a tiny in-memory stand-in for the parts of Firestore we use ----
class FakeSnapshot:
    def __init__(self, store, doc_id):
        self.id, self._store = doc_id, store
        self.reference = FakeDocRef(store, doc_id)

    def to_dict(self):
        return dict(self._store[self.id])


class FakeDocRef:
    def __init__(self, store, doc_id):
        self.id, self._store = doc_id, store

    def delete(self):
        self._store.pop(self.id, None)


class FakeCollection:
    def __init__(self):
        self.store, self._n, self._field, self._desc, self._limit = {}, 0, None, False, None

    def add(self, data):
        self._n += 1
        doc_id = f"doc{self._n}"
        self.store[doc_id] = dict(data)
        return None, FakeDocRef(self.store, doc_id)

    def document(self, doc_id):
        return FakeDocRef(self.store, doc_id)

    def order_by(self, field, direction="ASCENDING"):
        self._field, self._desc = field, direction == "DESCENDING"
        return self

    def limit(self, n):
        self._limit = n
        return self

    def stream(self):
        ids = list(self.store)
        if self._field:
            ids.sort(key=lambda i: self.store[i][self._field], reverse=self._desc)
        return [FakeSnapshot(self.store, i) for i in ids[: self._limit]]


class FakeClient:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        assert name == "users"
        return self

    def document(self, email):
        self._email = email
        return self

    # users/{email}/history
    def collection_history(self):
        return self.collections.setdefault(self._email, FakeCollection())


def _client():
    client = FakeClient()
    client.collection = lambda name: client  # users -> client
    original_document = client.document

    def document(email):
        original_document(email)
        return type("Doc", (), {"collection": lambda self, n: client.collection_history()})()

    client.document = document
    return client


CALLS = [{"tool": "search_mines", "args": {"province": "ON", "api_key": "SHOULD-NOT-BE-STORED"}, "rows": 3, "error": None}]


def test_save_and_list_newest_first_with_limit():
    c = _client()
    for i in range(5):
        history.save_question("A@Example.com", f"question {i}", f"answer {i}", CALLS, client=c)
        # make created_at strictly increasing
        coll = c.collections["a@example.com"]
        coll.store[f"doc{i + 1}"]["created_at"] = datetime(2026, 11, 24, tzinfo=timezone.utc) + timedelta(minutes=i)
    items = history.list_questions("a@example.com", limit=3, client=c)
    assert [i["question"] for i in items] == ["question 4", "question 3", "question 2"]


def test_only_tool_names_are_stored_and_text_is_capped():
    c = _client()
    history.save_question("a@example.com", "q" * 5000, "a" * 20000, CALLS, client=c)
    doc = next(iter(c.collections["a@example.com"].store.values()))
    assert doc["tools"] == ["search_mines"]
    assert "SHOULD-NOT-BE-STORED" not in str(doc)
    assert len(doc["question"]) == history.MAX_QUESTION_CHARS and len(doc["answer"]) == history.MAX_ANSWER_CHARS


def test_users_are_isolated_and_email_is_case_insensitive():
    c = _client()
    history.save_question("a@example.com", "mine", "x", [], client=c)
    history.save_question("B@example.com", "theirs", "y", [], client=c)
    assert [i["question"] for i in history.list_questions("A@EXAMPLE.COM", client=c)] == ["mine"]
    assert [i["question"] for i in history.list_questions("b@example.com", client=c)] == ["theirs"]


def test_delete_one_and_delete_all():
    c = _client()
    first = history.save_question("a@example.com", "one", "x", [], client=c)
    history.save_question("a@example.com", "two", "y", [], client=c)
    history.delete_question("a@example.com", first, client=c)
    assert [i["question"] for i in history.list_questions("a@example.com", client=c)] == ["two"]
    assert history.delete_all("a@example.com", client=c) == 1
    assert history.list_questions("a@example.com", client=c) == []


def test_enabled_flag(monkeypatch):
    monkeypatch.delenv("MINEMIND_ENABLE_ACCOUNTS", raising=False)
    assert history.enabled() is False
    monkeypatch.setenv("MINEMIND_ENABLE_ACCOUNTS", "1")
    assert history.enabled() is True


# ---- retry / fallback (needs the real google-genai package) ----
def test_agent_retries_then_falls_back(monkeypatch):
    pytest.importorskip("google.genai")
    from google.genai import errors

    from src.ai import gemini_agent

    class Busy(errors.APIError):
        def __init__(self, code):
            self.code = code

    calls = []

    class Models:
        def generate_content(self, model, contents, config):
            calls.append(model)
            if model == "main":
                raise Busy(503)
            return type("R", (), {"text": "ok from " + model})()

    client = type("C", (), {"models": Models()})()
    monkeypatch.setattr(gemini_agent, "_get_client", lambda: client)
    monkeypatch.setattr(gemini_agent, "MODEL", "main")
    monkeypatch.setattr(gemini_agent, "FALLBACK_MODELS", ["backup"])
    monkeypatch.setattr(gemini_agent.time, "sleep", lambda s: None)
    result = gemini_agent.ask("hello")
    assert calls == ["main", "main", "main", "backup"]
    assert result["ok"] and result["model"] == "backup" and result["answer"] == "ok from backup"


def test_agent_does_not_retry_real_errors(monkeypatch):
    pytest.importorskip("google.genai")
    from google.genai import errors

    from src.ai import gemini_agent

    class Denied(errors.APIError):
        def __init__(self, code):
            self.code = code

    calls = []

    class Models:
        def generate_content(self, model, contents, config):
            calls.append(model)
            raise Denied(403)

    client = type("C", (), {"models": Models()})()
    monkeypatch.setattr(gemini_agent, "_get_client", lambda: client)
    monkeypatch.setattr(gemini_agent, "FALLBACK_MODELS", ["backup"])
    result = gemini_agent.ask("hello")
    assert len(calls) == 1 and result["ok"] is False and "403" in result["answer"]
