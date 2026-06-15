"""
feedback_store.py
-----------------
SQLite-backed persistence layer for engineer feedback and maintenance logs
in the Maintenance Wizard project.
"""

import os
import sqlite3
import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..',
    'data',
    'feedback.db',
)
FEEDBACK_DB_PATH = os.getenv('FEEDBACK_DB_PATH', _DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
_CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    session_id        TEXT,
    query             TEXT,
    ai_response       TEXT,
    engineer_rating   INTEGER,
    engineer_comment  TEXT,
    was_helpful       INTEGER,
    corrected_action  TEXT
);
"""

_CREATE_MAINTENANCE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS maintenance_log (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    equipment_id     TEXT,
    action_taken     TEXT,
    outcome          TEXT,
    technician_name  TEXT,
    duration_hours   REAL
);
"""


class FeedbackStore:
    """
    SQLite-backed store for:
      - Engineer feedback on AI responses
      - Maintenance action logs
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path or FEEDBACK_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_connection(self) -> sqlite3.Connection:
        """Return a new SQLite connection with row_factory set."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not already exist."""
        try:
            with self._get_connection() as conn:
                conn.execute(_CREATE_FEEDBACK_TABLE)
                conn.execute(_CREATE_MAINTENANCE_LOG_TABLE)
                conn.commit()
        except Exception as e:
            raise RuntimeError(
                f"[FeedbackStore] Failed to initialise database at '{self.db_path}': {e}"
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.datetime.utcnow().isoformat(timespec='seconds') + 'Z'

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        return {k: row[k] for k in row.keys()}

    # ------------------------------------------------------------------
    # Feedback CRUD
    # ------------------------------------------------------------------

    def save_feedback(
        self,
        session_id: str,
        query: str,
        response: str,
        rating: int,
        comment: str,
        was_helpful: bool,
        corrected_action: Optional[str] = None,
    ) -> int:
        """
        Persist engineer feedback for a single query/response turn.

        Args:
            session_id       : Unique session/conversation identifier.
            query            : The engineer's original question.
            response         : The AI-generated response.
            rating           : Numeric rating (e.g. 1-5).
            comment          : Free-text engineer comment.
            was_helpful      : Whether the response was marked helpful.
            corrected_action : (optional) Engineer's corrected recommended action.

        Returns:
            Row ID (int) of the newly inserted row.
        """
        sql = """
        INSERT INTO feedback
            (timestamp, session_id, query, ai_response, engineer_rating,
             engineer_comment, was_helpful, corrected_action)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        self._now_iso(),
                        str(session_id),
                        str(query),
                        str(response),
                        int(rating),
                        str(comment),
                        int(bool(was_helpful)),
                        corrected_action,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            raise RuntimeError(f"[FeedbackStore] Failed to save feedback: {e}")

    # ------------------------------------------------------------------
    # Maintenance log CRUD
    # ------------------------------------------------------------------

    def save_maintenance_log(
        self,
        equipment_id: str,
        action: str,
        outcome: str,
        technician: str,
        duration: float,
    ) -> int:
        """
        Record a completed maintenance action.

        Args:
            equipment_id : Equipment identifier (e.g. 'EQ-001').
            action       : Description of the action taken.
            outcome      : Result of the action (e.g. 'Resolved', 'Partial fix').
            technician   : Name or ID of the technician.
            duration     : Time spent (hours).

        Returns:
            Row ID of the newly inserted row.
        """
        sql = """
        INSERT INTO maintenance_log
            (timestamp, equipment_id, action_taken, outcome, technician_name, duration_hours)
        VALUES
            (?, ?, ?, ?, ?, ?)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    sql,
                    (
                        self._now_iso(),
                        str(equipment_id),
                        str(action),
                        str(outcome),
                        str(technician),
                        float(duration),
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            raise RuntimeError(
                f"[FeedbackStore] Failed to save maintenance log: {e}"
            )

    # ------------------------------------------------------------------
    # Analytics / read methods
    # ------------------------------------------------------------------

    def get_feedback_stats(self) -> dict:
        """
        Compute aggregate statistics over all stored feedback.

        Returns:
            dict with keys:
                total_feedback    – total number of feedback rows
                avg_rating        – mean engineer rating (None if no rows)
                helpful_pct       – percentage of responses marked helpful
                recent_count_7days – rows inserted in the last 7 days
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as total, AVG(engineer_rating) as avg_r, "
                    "SUM(was_helpful) as helpful_sum FROM feedback"
                ).fetchone()

                total = row['total'] or 0
                avg_rating = round(row['avg_r'], 2) if row['avg_r'] is not None else None
                helpful_sum = row['helpful_sum'] or 0
                helpful_pct = round((helpful_sum / total) * 100.0, 1) if total > 0 else 0.0

                seven_days_ago = (
                    datetime.datetime.utcnow() - datetime.timedelta(days=7)
                ).isoformat(timespec='seconds') + 'Z'

                recent_row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM feedback WHERE timestamp >= ?",
                    (seven_days_ago,),
                ).fetchone()
                recent_count = recent_row['cnt'] or 0

            return {
                'total_feedback': total,
                'avg_rating': avg_rating,
                'helpful_pct': helpful_pct,
                'recent_count_7days': recent_count,
            }
        except Exception as e:
            raise RuntimeError(f"[FeedbackStore] Failed to get feedback stats: {e}")

    def get_recent_feedback(self, limit: int = 10) -> list:
        """
        Retrieve the most recent feedback rows.

        Args:
            limit: Maximum number of rows to return (default 10).

        Returns:
            List of dicts, newest first.
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM feedback ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            raise RuntimeError(f"[FeedbackStore] Failed to get recent feedback: {e}")

    def get_equipment_history(self, equipment_id: str) -> list:
        """
        Retrieve all maintenance log entries for a specific equipment ID.

        Args:
            equipment_id: The equipment identifier to look up.

        Returns:
            List of maintenance log dicts, oldest first.
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM maintenance_log WHERE equipment_id = ? ORDER BY id ASC",
                    (str(equipment_id),),
                ).fetchall()
            return [self._row_to_dict(r) for r in rows]
        except Exception as e:
            raise RuntimeError(
                f"[FeedbackStore] Failed to get history for equipment '{equipment_id}': {e}"
            )


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import tempfile

    print("=== FeedbackStore smoke-test ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, 'test_feedback.db')
        store = FeedbackStore(db_path=db_path)

        # Insert feedback
        fid = store.save_feedback(
            session_id='sess-001',
            query='What is the RUL of pump P-12?',
            response='Estimated RUL: 48 hours.',
            rating=4,
            comment='Accurate and helpful.',
            was_helpful=True,
        )
        print(f"  Saved feedback row id: {fid}")

        # Insert maintenance log
        mid = store.save_maintenance_log(
            equipment_id='EQ-P12',
            action='Replaced bearing and seal',
            outcome='Resolved – vibration returned to normal',
            technician='Rajesh Kumar',
            duration=3.5,
        )
        print(f"  Saved maintenance log row id: {mid}")

        # Stats
        stats = store.get_feedback_stats()
        print(f"  Feedback stats: {stats}")

        # Recent feedback
        recent = store.get_recent_feedback(limit=5)
        print(f"  Recent feedback: {len(recent)} row(s)")

        # Equipment history
        history = store.get_equipment_history('EQ-P12')
        print(f"  Equipment history for EQ-P12: {len(history)} row(s)")

    print("Smoke-test complete.")
