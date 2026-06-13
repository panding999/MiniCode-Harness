class Compactor:
    def __init__(self, repositories, threshold=30, keep=12):
        self.repositories, self.threshold, self.keep = repositories, threshold, keep

    def compact_if_needed(self, session_id: str):
        if self.repositories.messages.count(session_id) <= self.threshold:
            return
        recent = self.repositories.messages.list_recent(session_id, self.keep)
        summary = " | ".join(f"{m.role}: {m.content[:200]}" for m in recent)
        self.repositories.sessions.update_summary(session_id, summary)
