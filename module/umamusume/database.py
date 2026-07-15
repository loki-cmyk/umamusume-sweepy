import os
import sqlite3
import bot.base.log as logger

log = logger.get_logger(__name__)

DB_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), 'db'))
DB_FILE = os.path.join(DB_DIR, 'cultivate_data.db')


class CultivateDatabase:
    """SQLite-backed storage for cultivate training history.

    Holds a single persistent connection for its lifetime.
    Attach an instance to ``ctx.cultivate_detail.db`` so callers can
    query without importing standalone functions.
    """

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_FILE, timeout=10.0)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA foreign_keys=ON;")
        except Exception as e:
            log.warning(f"Failed to set database pragmas: {e}")
        self._init_tables()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _init_tables(self):
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS runs (
                        id TEXT PRIMARY KEY,
                        scenario_type TEXT DEFAULT 'unknown',
                        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        final_speed INTEGER,
                        final_stamina INTEGER,
                        final_power INTEGER,
                        final_guts INTEGER,
                        final_wits INTEGER,
                        final_sp INTEGER,
                        total_turns INTEGER
                    );
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS training_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        date INTEGER NOT NULL,
                        score REAL NOT NULL,
                        stat_only_score REAL NOT NULL,
                        energy REAL NOT NULL,
                        raw_stat_score REAL NOT NULL,
                        action TEXT DEFAULT 'unknown',
                        FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                    );
                """)
                self.conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_history_run_date
                    ON training_history(run_id, date);
                """)
                # Training analysis table
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS training_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        date INTEGER NOT NULL,
                        pre_speed INTEGER NOT NULL,
                        pre_stamina INTEGER NOT NULL,
                        pre_power INTEGER NOT NULL,
                        pre_guts INTEGER NOT NULL,
                        pre_wits INTEGER NOT NULL,
                        pre_sp INTEGER NOT NULL,
                        post_speed INTEGER,
                        post_stamina INTEGER,
                        post_power INTEGER,
                        post_guts INTEGER,
                        post_wits INTEGER,
                        post_sp INTEGER,
                        action TEXT NOT NULL,
                        max_score REAL,
                        chosen_stats REAL,
                        max_stats REAL,
                        greedy_type TEXT,
                        is_override INTEGER,
                        override_reason TEXT,
                        FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                    );
                """)
                self.conn.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_run_date
                    ON training_analysis(run_id, date);
                """)
        except Exception as e:
            log.error(f"Failed to initialize SQLite tables: {e}")
            raise

    def close(self):
        """Close the underlying connection."""
        try:
            self.conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Insert helpers
    # ------------------------------------------------------------------

    def ensure_run_exists(self, run_id, scenario_type='unknown'):
        if not run_id:
            run_id = 'unknown_run'
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT OR IGNORE INTO runs (id, scenario_type) VALUES (?, ?)",
                    (run_id, scenario_type),
                )
        except Exception as e:
            log.error(f"Failed to insert run {run_id}: {e}")

    def save_training_entry(self, run_id, date, score, stat_only, energy, raw_stat,
                            action='unknown', scenario_type='unknown'):
        if not run_id:
            run_id = 'unknown_run'
        self.ensure_run_exists(run_id, scenario_type)
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO training_history
                    (run_id, date, score, stat_only_score, energy, raw_stat_score, action)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (run_id, date, score, stat_only, energy, raw_stat, action))
        except Exception as e:
            log.error(f"Failed to save training entry for run {run_id} turn date {date}: {e}")

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_recent_history(self, limit=2000):
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT score, stat_only_score, energy, raw_stat_score, date, action
                FROM training_history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            rows.reverse()  # chronological order

            return {
                'score_history': [r[0] for r in rows],
                'stat_only_history': [r[1] for r in rows],
                'energy_history': [r[2] for r in rows],
                'raw_stat_history': [r[3] for r in rows],
                'date_history': [r[4] for r in rows],
                'action_history': [r[5] for r in rows],
            }
        except Exception as e:
            log.error(f"Failed to fetch recent history from database: {e}")
            return {
                'score_history': [],
                'stat_only_history': [],
                'energy_history': [],
                'raw_stat_history': [],
                'date_history': [],
                'action_history': [],
            }

    def get_total_history_count(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_history")
            row = cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            log.error(f"Failed to get total history count: {e}")
            return 0

    def get_latest_date(self):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT date FROM training_history ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            log.error(f"Failed to get latest date: {e}")
            return None

    def clear_all_data(self):
        try:
            with self.conn:
                self.conn.execute("DELETE FROM training_analysis")
                self.conn.execute("DELETE FROM training_history")
                self.conn.execute("DELETE FROM runs")
            log.info("SQLite database cleared successfully")
            return True
        except Exception as e:
            log.error(f"Failed to clear SQLite data: {e}")
            return False

    # ------------------------------------------------------------------
    # Percentile calculations (SQL-backed)
    # ------------------------------------------------------------------

    def get_best_percentile(self, best_score):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_history")
            total = cursor.fetchone()[0]
            if total < 16:
                return None

            cursor.execute("""
                WITH recent_scores AS (
                    SELECT score FROM training_history ORDER BY id DESC LIMIT 2000
                )
                SELECT COUNT(*) FROM recent_scores WHERE score < ?
            """, (best_score,))
            below_count = cursor.fetchone()[0]

            limit = min(total, 2000)
            return (below_count / limit) * 100
        except Exception as e:
            log.error(f"Error calculating best percentile in DB: {e}")
            return None

    def get_stat_only_percentile(self, best_score):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_history")
            total = cursor.fetchone()[0]
            if total < 16:
                return None

            cursor.execute("""
                WITH recent_stats AS (
                    SELECT stat_only_score FROM training_history ORDER BY id DESC LIMIT 2000
                )
                SELECT COUNT(*) FROM recent_stats WHERE stat_only_score < ?
            """, (best_score,))
            below_count = cursor.fetchone()[0]

            limit = min(total, 2000)
            return (below_count / limit) * 100
        except Exception as e:
            log.error(f"Error calculating stat-only percentile in DB: {e}")
            return None

    def get_date_weighted_percentile(self, current_date, current_raw):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_history")
            total = cursor.fetchone()[0]
            if total < 8:
                return None

            cursor.execute("""
                WITH recent_history AS (
                    SELECT raw_stat_score, date FROM training_history ORDER BY id DESC LIMIT 2000
                )
                SELECT
                    SUM(CASE WHEN raw_stat_score < ? THEN 1.0 / (1.0 + abs(date - ?)) ELSE 0.0 END),
                    SUM(1.0 / (1.0 + abs(date - ?)))
                FROM recent_history
                WHERE abs(date - ?) <= 12
            """, (current_raw, current_date, current_date, current_date))
            row = cursor.fetchone()
            if not row or row[1] is None or row[1] <= 0:
                return 50.0
            return (row[0] / row[1]) * 100
        except Exception as e:
            log.error(f"Error calculating date-weighted percentile in DB: {e}")
            return None

    def get_date_weighted_score_percentile(self, current_date, current_score):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM training_history")
            total = cursor.fetchone()[0]
            if total < 8:
                return None

            cursor.execute("""
                WITH recent_history AS (
                    SELECT score, date FROM training_history ORDER BY id DESC LIMIT 2000
                )
                SELECT
                    SUM(CASE WHEN score < ? THEN 1.0 / (1.0 + abs(date - ?)) ELSE 0.0 END),
                    SUM(1.0 / (1.0 + abs(date - ?)))
                FROM recent_history
                WHERE abs(date - ?) <= 12
            """, (current_score, current_date, current_date, current_date))
            row = cursor.fetchone()
            if not row or row[1] is None or row[1] <= 0:
                return 50.0
            return (row[0] / row[1]) * 100
        except Exception as e:
            log.error(f"Error calculating date-weighted score percentile in DB: {e}")
            return None

    # ------------------------------------------------------------------
    # Training analysis
    # ------------------------------------------------------------------

    def save_training_analysis(self, run_id, date, pre_stats, action,
                               max_score=None, chosen_stats=None, max_stats=None,
                               greedy_type=None, is_override=0, override_reason=None):
        """Save a training analysis snapshot for the given turn."""
        if not run_id:
            run_id = 'unknown_run'
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT OR REPLACE INTO training_analysis
                    (run_id, date, pre_speed, pre_stamina, pre_power, pre_guts, pre_wits, pre_sp,
                     action, max_score, chosen_stats, max_stats, greedy_type, is_override, override_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, date,
                      pre_stats.get('speed', 0), pre_stats.get('stamina', 0),
                      pre_stats.get('power', 0), pre_stats.get('guts', 0),
                      pre_stats.get('wits', 0), pre_stats.get('sp', 0),
                      action, max_score, chosen_stats, max_stats,
                      greedy_type, is_override, override_reason))
        except Exception as e:
            log.error(f"Failed to save training analysis for run {run_id} turn {date}: {e}")

    def update_analysis_post_stats(self, run_id, date, post_stats):
        """Update the post-action stats for a previously saved analysis row."""
        if not run_id:
            return
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE training_analysis
                    SET post_speed=?, post_stamina=?, post_power=?, post_guts=?, post_wits=?, post_sp=?
                    WHERE run_id=? AND date=?
                """, (post_stats.get('speed', 0), post_stats.get('stamina', 0),
                      post_stats.get('power', 0), post_stats.get('guts', 0),
                      post_stats.get('wits', 0), post_stats.get('sp', 0),
                      run_id, date))
        except Exception as e:
            log.error(f"Failed to update post-stats for run {run_id} turn {date}: {e}")

    def save_run_final_stats(self, run_id, final_stats, total_turns):
        """Update a run row with final stats when the cultivation finishes."""
        if not run_id:
            return
        try:
            with self.conn:
                self.conn.execute("""
                    UPDATE runs
                    SET final_speed=?, final_stamina=?, final_power=?,
                        final_guts=?, final_wits=?, final_sp=?, total_turns=?
                    WHERE id=?
                """, (final_stats.get('speed', 0), final_stats.get('stamina', 0),
                      final_stats.get('power', 0), final_stats.get('guts', 0),
                      final_stats.get('wits', 0), final_stats.get('sp', 0),
                      total_turns, run_id))
        except Exception as e:
            log.error(f"Failed to save run final stats for {run_id}: {e}")

def get_database() -> CultivateDatabase:
    """Create a short-lived CultivateDatabase for use outside ctx (e.g. API endpoints).

    Caller is responsible for calling .close() when done.
    """
    return CultivateDatabase()
