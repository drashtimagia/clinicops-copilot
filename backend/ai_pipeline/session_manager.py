from typing import Dict, Any, Optional
import time

class SessionManager:
    def __init__(self, expires_after: int = 3600):
        # session_id -> { "data": {}, "last_accessed": float }
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._expires_after = expires_after

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """Retrieve session data, initializing if not exists."""
        self._cleanup()
        
        if session_id not in self._sessions:
            print(f"[SessionManager] Creating new session: {session_id}")
            self._sessions[session_id] = {
                "data": {
                    "staff_role": None,
                    "room": None,
                    "machine": None,
                    "problem": None,
                    "issue_details": [],
                    "troubleshooting_stage": "intake",
                    "last_question": None,
                    "last_handoff": {},
                    "escalate": False,
                    "conversation_history": []
                },
                "last_accessed": time.time()
            }
        
        self._sessions[session_id]["last_accessed"] = time.time()
        return self._sessions[session_id]["data"]

    def update_session(self, session_id: str, updates: Dict[str, Any]):
        """Update session data with new values."""
        session = self.get_session(session_id)
        # Deep update for keys
        for key, value in updates.items():
            session[key] = value
        self._sessions[session_id]["last_accessed"] = time.time()

    def _cleanup(self):
        """Simple expiry-based cleanup."""
        now = time.time()
        to_delete = [
            sid for sid, sdata in self._sessions.items()
            if now - sdata["last_accessed"] > self._expires_after
        ]
        for sid in to_delete:
            print(f"[SessionManager] Expiring session: {sid}")
            del self._sessions[sid]

# Global instance
session_manager = SessionManager()
