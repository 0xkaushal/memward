"""
Tests for connectors/claude_code/session_start_hook.py

Covers:
- read_new_lines / extract_content (shared logic with stop_hook, light coverage)
- reconcile_missed_sessions: skips current session, processes missed sessions,
  handles missing projects dir, handles unreadable transcript gracefully,
  does NOT advance checkpoint when ingest fails
- fetch_and_inject_memories: writes {"context": ...} to stdout on success,
  silent when server is unavailable, silent when no approved memories exist
- main() flow: empty stdin, invalid JSON, normal reconcile + inject sequence
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "connectors" / "claude_code"))
import session_start_hook


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_transcript(directory: Path, session_id: str, turns: list[dict]) -> Path:
    f = directory / f"{session_id}.jsonl"
    f.write_text("\n".join(json.dumps(t) for t in turns), encoding="utf-8")
    return f


def user_turn(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant_turn(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": text}}


# ── reconcile_missed_sessions ─────────────────────────────────────────────────

def test_reconcile_skips_current_session(tmp_path, monkeypatch):
    """The current session must never be reconciled — the Stop hook owns it."""
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    make_transcript(projects, "current-session", [user_turn("do not ingest me")])

    with patch("session_start_hook.post_to_ingest") as mock_post:
        session_start_hook.reconcile_missed_sessions("current-session", "startup")
    mock_post.assert_not_called()


def test_reconcile_processes_missed_session(tmp_path, monkeypatch):
    """A past session with unprocessed lines is ingested."""
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    make_transcript(projects, "old-session", [user_turn("missed fact")])

    with patch("session_start_hook.post_to_ingest", return_value=True) as mock_post:
        session_start_hook.reconcile_missed_sessions("new-session", "startup")

    mock_post.assert_called_once()
    args = mock_post.call_args[0]
    assert "missed fact" in args[1]  # content argument


def test_reconcile_advances_checkpoint_on_success(tmp_path, monkeypatch):
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    make_transcript(projects, "past", [user_turn("fact 1"), assistant_turn("ok")])

    with patch("session_start_hook.post_to_ingest", return_value=True):
        session_start_hook.reconcile_missed_sessions("current", "resume")

    assert session_start_hook.load_checkpoint("past") == 2


def test_reconcile_does_not_advance_checkpoint_on_failure(tmp_path, monkeypatch):
    """If ingest fails, checkpoint must NOT advance so the retry can recover it."""
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    make_transcript(projects, "past-fail", [user_turn("important")])

    with patch("session_start_hook.post_to_ingest", return_value=False):
        session_start_hook.reconcile_missed_sessions("current", "startup")

    assert session_start_hook.load_checkpoint("past-fail") == 0


def test_reconcile_skips_already_processed(tmp_path, monkeypatch):
    """Sessions whose checkpoint equals total line count are skipped."""
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    make_transcript(projects, "done-session", [user_turn("already ingested")])
    session_start_hook.save_checkpoint("done-session", 1)  # already at end

    with patch("session_start_hook.post_to_ingest") as mock_post:
        session_start_hook.reconcile_missed_sessions("current", "startup")
    mock_post.assert_not_called()


def test_reconcile_missing_projects_dir(tmp_path, monkeypatch):
    """If ~/.claude/projects/ doesn't exist, reconcile exits cleanly."""
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", tmp_path / "nonexistent")
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", tmp_path / "cp")
    # Should not raise
    session_start_hook.reconcile_missed_sessions("current", "startup")


def test_reconcile_handles_unreadable_transcript(tmp_path, monkeypatch):
    """A transcript that raises on read is skipped silently."""
    projects = tmp_path / "projects"
    projects.mkdir()
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(session_start_hook, "CHECKPOINT_DIR", cp_dir)
    monkeypatch.setattr(session_start_hook, "CLAUDE_PROJECTS_DIR", projects)

    bad = projects / "bad-session.jsonl"
    bad.write_text("irrelevant")

    with patch("session_start_hook.read_new_lines", side_effect=OSError("permission denied")):
        # Should not raise
        session_start_hook.reconcile_missed_sessions("current", "startup")


# ── fetch_and_inject_memories ─────────────────────────────────────────────────

def test_fetch_and_inject_writes_context_to_stdout(monkeypatch, capsys):
    memories = {
        "results": [
            {"category": "code", "source": "claude_code", "content": "use sqlalchemy"},
            {"category": "personal", "source": "copilot", "content": "prefer type hints"},
        ]
    }
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(memories).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        session_start_hook.fetch_and_inject_memories()

    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert "context" in data
    assert "use sqlalchemy" in data["context"]
    assert "prefer type hints" in data["context"]


def test_fetch_and_inject_silent_when_server_down(monkeypatch, capsys):
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        session_start_hook.fetch_and_inject_memories()
    assert capsys.readouterr().out == ""


def test_fetch_and_inject_silent_when_no_memories(monkeypatch, capsys):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"results": []}).encode()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_resp):
        session_start_hook.fetch_and_inject_memories()
    assert capsys.readouterr().out == ""


def test_fetch_and_inject_silent_on_timeout(monkeypatch, capsys):
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        session_start_hook.fetch_and_inject_memories()
    assert capsys.readouterr().out == ""


# ── main() flow ───────────────────────────────────────────────────────────────

def test_main_empty_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: ""))
    with pytest.raises(SystemExit) as exc:
        session_start_hook.main()
    assert exc.value.code == 0


def test_main_invalid_json(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: "NOT JSON"))
    with pytest.raises(SystemExit) as exc:
        session_start_hook.main()
    assert exc.value.code == 0


def test_main_calls_reconcile_and_inject(monkeypatch):
    event = json.dumps({"session_id": "s1", "source": "startup"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))

    with patch("session_start_hook.reconcile_missed_sessions") as mock_rec, \
         patch("session_start_hook.fetch_and_inject_memories") as mock_inj:
        session_start_hook.main()

    mock_rec.assert_called_once_with("s1", "startup")
    mock_inj.assert_called_once()


def test_main_defaults_source_to_startup(monkeypatch):
    """If 'source' key is absent from event, defaults to 'startup'."""
    event = json.dumps({"session_id": "s2"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))

    with patch("session_start_hook.reconcile_missed_sessions") as mock_rec, \
         patch("session_start_hook.fetch_and_inject_memories"):
        session_start_hook.main()

    assert mock_rec.call_args[0][1] == "startup"
