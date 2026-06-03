import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from .config import (
    CHAT_SESSION_MAX_TURNS,
    CHAT_SESSION_TTL_SECONDS,
)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            if time.time() > session["expires_at"]:
                del self._sessions[session_id]
                return None
            session["expires_at"] = time.time() + CHAT_SESSION_TTL_SECONDS
            self._sessions.move_to_end(session_id)
            return session

    def create(self, session_id: str, destination_id: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            self._sessions[session_id] = {
                "destination_id": destination_id,
                "turns": [],
                "expires_at": time.time() + CHAT_SESSION_TTL_SECONDS,
            }
            self._sessions.move_to_end(session_id)
            return self._sessions[session_id]

    def get_or_create(self, session_id: str, destination_id: Optional[int] = None) -> Dict[str, Any]:
        session = self.get(session_id)
        if session is not None:
            return session
        return self.create(session_id, destination_id=destination_id)

    def append_turn(self, session_id: str, user_message: str, assistant_message: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session["turns"].append(
                {"user": user_message, "assistant": assistant_message}
            )
            if len(session["turns"]) > CHAT_SESSION_MAX_TURNS:
                session["turns"] = session["turns"][-CHAT_SESSION_MAX_TURNS:]
            session["expires_at"] = time.time() + CHAT_SESSION_TTL_SECONDS
            self._sessions.move_to_end(session_id)

    def build_history(self, session_id: str) -> List[Dict[str, str]]:
        session = self.get(session_id)
        if not session:
            return []
        history: List[Dict[str, str]] = []
        for turn in session["turns"]:
            history.append({"role": "user", "content": turn["user"]})
            history.append({"role": "assistant", "content": turn["assistant"]})
        return history

    def touch(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session["expires_at"] = time.time() + CHAT_SESSION_TTL_SECONDS
                self._sessions.move_to_end(session_id)

    def delete(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def stats(self) -> Dict[str, int]:
        now = time.time()
        total = len(self._sessions)
        active = sum(1 for session in self._sessions.values() if session["expires_at"] > now)
        return {"total": total, "active": active}


session_store = SessionStore()
