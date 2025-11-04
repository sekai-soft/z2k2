"""
Session manager for Twitter OAuth credentials.
Reads and manages sessions from sessions.jsonl file.
"""

import json
from pathlib import Path
from typing import List
from dataclasses import dataclass


@dataclass
class _TwitterSession:
    """Twitter OAuth session credentials."""
    oauth_token: str
    oauth_token_secret: str


class SessionManager:
    """
    Manages Twitter OAuth sessions from sessions.jsonl file.

    Loads sessions from a JSONL file (one JSON object per line) where each
    session contains oauth_token and oauth_token_secret.
    """

    def __init__(self, sessions_file: str = "sessions.jsonl"):
        """
        Initialize session manager.

        Args:
            sessions_file: Path to sessions JSONL file (relative to repo root)
        """
        self.sessions: List[_TwitterSession] = []
        self._current_index = 0
        self._load_sessions(sessions_file)

    def _load_sessions(self, sessions_file: str):
        """
        Load sessions from JSONL file.

        Args:
            sessions_file: Path to sessions file
        """
        # Find repo root (where sessions.jsonl is located)
        sessions_path = Path(sessions_file)

        # If relative path, resolve from current working directory
        if not sessions_path.is_absolute():
            # Try current directory first
            if not sessions_path.exists():
                # Try parent directories (up to 3 levels)
                for parent in [Path.cwd()] + list(Path.cwd().parents)[:3]:
                    potential_path = parent / sessions_file
                    if potential_path.exists():
                        sessions_path = potential_path
                        break

        if not sessions_path.exists():
            raise FileNotFoundError(
                f"Sessions file not found: {sessions_file}. "
                "Please create a sessions.jsonl file in the repository root."
            )

        # Read JSONL file (one JSON object per line)
        with open(sessions_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    session_data = json.loads(line)
                    session = _TwitterSession(
                        oauth_token=session_data["oauth_token"],
                        oauth_token_secret=session_data["oauth_token_secret"]
                    )
                    self.sessions.append(session)
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"Warning: Invalid session on line {line_num}: {e}")
                    continue

        if not self.sessions:
            raise ValueError(
                f"No valid sessions found in {sessions_file}. "
                "Please add at least one valid session."
            )

        print(f"Loaded {len(self.sessions)} session(s) from {sessions_path}")

    def get_session(self) -> _TwitterSession:
        """
        Get next session using round-robin strategy.

        Returns:
            _TwitterSession with oauth credentials
        """
        if not self.sessions:
            raise RuntimeError("No sessions available")

        session = self.sessions[self._current_index]
        self._current_index = (self._current_index + 1) % len(self.sessions)
        return session
