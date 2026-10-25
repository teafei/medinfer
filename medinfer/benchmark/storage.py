import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path):
        self.path = str(Path(path).expanduser())
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, status TEXT NOT NULL,
                config TEXT NOT NULL, summary TEXT, error TEXT
            );
            CREATE TABLE IF NOT EXISTS records (
                run_id TEXT NOT NULL REFERENCES runs(id), sequence INTEGER NOT NULL,
                data TEXT NOT NULL, PRIMARY KEY (run_id, sequence)
            );
            """)

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, run_id, created, config):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO runs VALUES (?,?,?,?,NULL,NULL)",
                (run_id, created, "running", json.dumps(config)),
            )

    def append(self, run_id, sequence, record):
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO records VALUES (?,?,?)", (run_id, sequence, json.dumps(record))
            )

    def finish(self, run_id, status, summary=None, error=None):
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status=?, summary=?, error=? WHERE id=?",
                (status, json.dumps(summary) if summary is not None else None, error, run_id),
            )

    def interrupt_stale(self):
        with self.connect() as conn:
            conn.execute(
                "UPDATE runs SET status='interrupted', error='service restarted' "
                "WHERE status='running'"
            )

    def list(self):
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 200").fetchall()
        return [self._decode(r) for r in rows]

    @staticmethod
    def _decode(row):
        obj = dict(row)
        for name in ("config", "summary"):
            obj[name] = json.loads(obj[name]) if obj[name] else None
        return obj

    def get(self, run_id):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                return None
            records = conn.execute(
                "SELECT data FROM records WHERE run_id=? ORDER BY sequence", (run_id,)
            ).fetchall()
        return {**self._decode(row), "records": [json.loads(r[0]) for r in records]}
