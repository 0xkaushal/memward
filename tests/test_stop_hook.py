"""
Tests for connectors/claude_code/stop_hook.py

Covers:
- read_new_lines: normal read, incremental (from offset), empty file, missing file
- extract_content: plain string content, list content blocks, tool_result blocks,
  unknown turn types skipped, empty content skipped
- post_to_ingest: success (202), API unavailable, timeout, non-202 response
- checkpoint load/save round-trip
- main() flow: no stdin, invalid JSON, missing transcript_path,
  no new turns, content extracted but API down (checkpoint NOT advanced),
  successful end-to-end (checkpoint IS advanced),
  duplicate delivery is safe (idempotency handled server-side)
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add connectors to path so we can import the module directly
sys.path.insert(0, str(Path(__file__).parent.parent / "connectors" / "claude_code"))
import stop_hook


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_transcript(tmp_path: Path, turns: list[dict]) -> Path:
    f = tmp_path / "session.jsonl"
    f.write_text("\n".join(json.dumps(t) for t in turns), encoding="utf-8")
    return f


def user_turn(text: str) -> dict:
    return {"type": "user", "message": {"role": "user", "content": text}}


def assistant_turn(text: str) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": text}}


def assistant_turn_blocks(blocks: list[dict]) -> dict:
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}


# ── read_new_lines ─────────────────────────────────────────────────────────────

def test_read_new_lines_full(tmp_path):
    f = make_transcript(tmp_path, [user_turn("hello"), assistant_turn("hi")])
    lines, total = stop_hook.read_new_lines(str(f), 0)
    assert len(lines) == 2
    assert total == 2


def test_read_new_lines_incremental(tmp_path):
    f = make_transcript(tmp_path, [user_turn("first"), assistant_turn("second"), user_turn("third")])
    lines, total = stop_hook.read_new_lines(str(f), 2)
    assert len(lines) == 1
    assert lines[0]["message"]["content"] == "third"
    assert total == 3


def test_read_new_lines_no_new_turns(tmp_path):
    f = make_transcript(tmp_path, [user_turn("only")])
    lines, total = stop_hook.read_new_lines(str(f), 1)
    assert lines == []
    assert total == 1


def test_read_new_lines_missing_file(tmp_path):
    lines, total = stop_hook.read_new_lines(str(tmp_path / "nonexistent.jsonl"), 0)
    assert lines == []
    assert total == 0


def test_read_new_lines_skips_invalid_json(tmp_path):
    f = tmp_path / "s.jsonl"
    f.write_text('{"type":"user","message":{"role":"user","content":"ok"}}\nNOT JSON\n', encoding="utf-8")
    lines, total = stop_hook.read_new_lines(str(f), 0)
    assert len(lines) == 1
    assert total == 2


# ── extract_content ───────────────────────────────────────────────────────────

def test_extract_content_plain_strings():
    turns = [user_turn("what is pgvector"), assistant_turn("it is a vector extension")]
    result = stop_hook.extract_content(turns)
    assert "[user]: what is pgvector" in result
    assert "[assistant]: it is a vector extension" in result


def test_extract_content_list_blocks():
    turn = assistant_turn_blocks([
        {"type": "text", "text": "Here is the answer"},
        {"type": "tool_use", "name": "bash"},  # should be ignored
    ])
    result = stop_hook.extract_content([turn])
    assert "Here is the answer" in result
    assert "tool_use" not in result


def test_extract_content_tool_result_blocks():
    turn = {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "content": [{"type": "text", "text": "stdout output"}]},
            ],
        },
    }
    result = stop_hook.extract_content([turn])
    assert "stdout output" in result


def test_extract_content_skips_unknown_turn_types():
    turns = [
        {"type": "system", "message": {"role": "system", "content": "system prompt"}},
        user_turn("real message"),
    ]
    result = stop_hook.extract_content(turns)
    assert "system prompt" not in result
    assert "real message" in result


def test_extract_content_skips_empty_content():
    turns = [user_turn(""), assistant_turn("   "), user_turn("actual content")]
    result = stop_hook.extract_content(turns)
    assert result.count("[") == 1  # only the non-empty turn


# ── post_to_ingest ────────────────────────────────────────────────────────────

def test_post_to_ingest_success():
    mock_resp = MagicMock()
    mock_resp.status = 202
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = stop_hook.post_to_ingest("sess-1", "/repo", "some content")
    assert result is True


def test_post_to_ingest_api_unavailable():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        result = stop_hook.post_to_ingest("sess-1", "/repo", "some content")
    assert result is False


def test_post_to_ingest_timeout():
    import socket
    with patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")):
        result = stop_hook.post_to_ingest("sess-1", "/repo", "some content")
    assert result is False


def test_post_to_ingest_non_202_response():
    mock_resp = MagicMock()
    mock_resp.status = 500
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        result = stop_hook.post_to_ingest("sess-1", "/repo", "some content")
    assert result is False


# ── checkpoint ────────────────────────────────────────────────────────────────

def test_checkpoint_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", tmp_path)
    stop_hook.save_checkpoint("sess-abc", 42)
    assert stop_hook.load_checkpoint("sess-abc") == 42


def test_checkpoint_missing_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", tmp_path)
    assert stop_hook.load_checkpoint("nonexistent-session") == 0


def test_checkpoint_corrupt_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", tmp_path)
    (tmp_path / "bad-session.json").write_text("NOT JSON")
    assert stop_hook.load_checkpoint("bad-session") == 0


# ── main() flow ───────────────────────────────────────────────────────────────

def test_main_empty_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: ""))
    with pytest.raises(SystemExit) as exc:
        stop_hook.main()
    assert exc.value.code == 0


def test_main_invalid_json_stdin(monkeypatch):
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: "NOT JSON"))
    with pytest.raises(SystemExit) as exc:
        stop_hook.main()
    assert exc.value.code == 0


def test_main_missing_transcript_path(monkeypatch):
    event = json.dumps({"session_id": "s1", "cwd": "/repo"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with pytest.raises(SystemExit) as exc:
        stop_hook.main()
    assert exc.value.code == 0


def test_main_no_new_turns(tmp_path, monkeypatch):
    """Checkpoint already at end of file — nothing to ingest."""
    f = make_transcript(tmp_path, [user_turn("already seen")])
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", cp_dir)
    stop_hook.save_checkpoint("s1", 1)  # already processed 1 line

    event = json.dumps({"session_id": "s1", "transcript_path": str(f), "cwd": "/repo"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with patch("stop_hook.post_to_ingest") as mock_post:
        with pytest.raises(SystemExit):
            stop_hook.main()
        mock_post.assert_not_called()


def test_main_api_down_does_not_advance_checkpoint(tmp_path, monkeypatch):
    """When ingest fails, checkpoint must NOT advance so the data can be retried."""
    f = make_transcript(tmp_path, [user_turn("important fact")])
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", cp_dir)

    event = json.dumps({"session_id": "s2", "transcript_path": str(f), "cwd": "/repo"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with patch("stop_hook.post_to_ingest", return_value=False):
        stop_hook.main()

    # Checkpoint must still be 0 — data not yet durably accepted
    assert stop_hook.load_checkpoint("s2") == 0


def test_main_success_advances_checkpoint(tmp_path, monkeypatch):
    """When ingest succeeds, checkpoint advances to total line count."""
    turns = [user_turn("use sqlalchemy"), assistant_turn("noted")]
    f = make_transcript(tmp_path, turns)
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", cp_dir)

    event = json.dumps({"session_id": "s3", "transcript_path": str(f), "cwd": "/repo"})
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with patch("stop_hook.post_to_ingest", return_value=True):
        stop_hook.main()

    assert stop_hook.load_checkpoint("s3") == 2


def test_main_duplicate_delivery_safe(tmp_path, monkeypatch):
    """Replaying the same event twice is safe — second call finds no new lines."""
    turns = [user_turn("use black formatter")]
    f = make_transcript(tmp_path, turns)
    cp_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(stop_hook, "CHECKPOINT_DIR", cp_dir)

    event = json.dumps({"session_id": "s4", "transcript_path": str(f), "cwd": "/repo"})
    call_count = 0

    def fake_post(session_id, cwd, content):
        nonlocal call_count
        call_count += 1
        return True

    # First delivery — processes 1 line, advances checkpoint to 1
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with patch("stop_hook.post_to_ingest", side_effect=fake_post):
        stop_hook.main()

    assert stop_hook.load_checkpoint("s4") == 1

    # Second delivery — checkpoint already at 1, no new lines, exits early
    monkeypatch.setattr("sys.stdin", MagicMock(read=lambda: event))
    with patch("stop_hook.post_to_ingest", side_effect=fake_post):
        with pytest.raises(SystemExit):
            stop_hook.main()

    # post_to_ingest must have been called exactly once total
    assert call_count == 1
