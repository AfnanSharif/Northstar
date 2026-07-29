from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Protocol


class Memory(Protocol):
    def remember(self, user_id: str, question: str, answer: str) -> None: ...
    def recent(self, user_id: str, limit: int = 5) -> list[tuple[str, str]]: ...
    def contextual(self, user_id: str, query: str, limit: int = 5) -> list[tuple[str, str]]: ...
    def set_preference(self, user_id: str, key: str, value: str) -> None: ...
    def preferences(self, user_id: str) -> dict[str, str]: ...


class SQLiteMemory:
    def __init__(self, path: str | Path = "data/wealth_memory.sqlite3") -> None:
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, user_id TEXT, question TEXT, answer TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE INDEX IF NOT EXISTS messages_user_id_id ON messages(user_id, id)")
            db.execute("CREATE TABLE IF NOT EXISTS preferences(user_id TEXT, key TEXT, value TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,key))")

    def remember(self, user_id: str, question: str, answer: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT INTO messages(user_id,question,answer) VALUES(?,?,?)", (user_id, question, answer))

    def recent(self, user_id: str, limit: int = 5) -> list[tuple[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT question,answer FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?", (user_id, limit)).fetchall()
        return list(reversed(rows))

    def contextual(self, user_id: str, query: str, limit: int = 5) -> list[tuple[str, str]]:
        # SQLite is the dependency-free recency fallback; Chroma provides semantic ranking.
        return self.recent(user_id, limit)

    def set_preference(self, user_id: str, key: str, value: str) -> None:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO preferences(user_id,key,value) VALUES(?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
                (user_id, key, value),
            )

    def preferences(self, user_id: str) -> dict[str, str]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT key,value FROM preferences WHERE user_id=? ORDER BY key", (user_id,)).fetchall()
        return dict(rows)


class ChromaMemory:
    def __init__(self, path: str = "chroma_data") -> None:
        import chromadb

        self.collection = chromadb.PersistentClient(path=path).get_or_create_collection("wealth_memory")

    def remember(self, user_id: str, question: str, answer: str) -> None:
        identity = hashlib.sha256(f"{user_id}:{question}:{answer}".encode()).hexdigest()
        self.collection.upsert(ids=[identity], documents=[f"Q: {question}\nA: {answer}"], metadatas=[{"user_id": user_id, "kind": "conversation"}])

    def recent(self, user_id: str, limit: int = 5) -> list[tuple[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        result = self.collection.get(where={"$and": [{"user_id": user_id}, {"kind": "conversation"}]}, limit=limit, include=["documents"])
        pairs = []
        for document in result.get("documents") or []:
            question, _, answer = document.partition("\nA: ")
            pairs.append((question.removeprefix("Q: "), answer))
        return pairs

    def contextual(self, user_id: str, query: str, limit: int = 5) -> list[tuple[str, str]]:
        if not query.strip() or not 1 <= limit <= 100:
            raise ValueError("query must be non-empty and limit must be between 1 and 100")
        result = self.collection.query(
            query_texts=[query],
            n_results=limit,
            where={"$and": [{"user_id": user_id}, {"kind": "conversation"}]},
            include=["documents"],
        )
        pairs = []
        nested_documents = result.get("documents") or [[]]
        for document in nested_documents[0] or []:
            question, _, answer = document.partition("\nA: ")
            pairs.append((question.removeprefix("Q: "), answer))
        return pairs

    def set_preference(self, user_id: str, key: str, value: str) -> None:
        identity = hashlib.sha256(f"preference:{user_id}:{key}".encode()).hexdigest()
        self.collection.upsert(
            ids=[identity],
            documents=[f"Preference {key}: {value}"],
            metadatas=[{"user_id": user_id, "kind": "preference", "key": key, "value": value}],
        )

    def preferences(self, user_id: str) -> dict[str, str]:
        result = self.collection.get(
            where={"$and": [{"user_id": user_id}, {"kind": "preference"}]},
            include=["metadatas"],
        )
        return {
            str(item["key"]): str(item["value"])
            for item in result.get("metadatas") or []
            if item and item.get("key") is not None and item.get("value") is not None
        }
