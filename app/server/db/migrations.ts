/**
 * Schema migrations, applied in order at startup by migrate.ts.
 *
 * Every statement is idempotent (IF NOT EXISTS) so a restart is a no-op, and
 * the applied version is recorded so a future migration that is not idempotent
 * can rely on running once. The app's service principal creates the schema on
 * the first deploy and therefore owns it - never run this locally before the
 * first deploy (see app/README.md).
 */

export interface Migration {
  version: number;
  name: string;
  sql: string;
}

export const migrations: Migration[] = [
  {
    version: 1,
    name: 'init',
    sql: `
      CREATE SCHEMA IF NOT EXISTS study;

      CREATE TABLE IF NOT EXISTS study.schema_migrations (
        version     INT PRIMARY KEY,
        name        TEXT NOT NULL,
        applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
      );

      CREATE TABLE IF NOT EXISTS study.users (
        user_id       TEXT PRIMARY KEY,
        display_name  TEXT,
        last_area     TEXT CHECK (last_area IN ('learn', 'test')),
        first_seen    TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_seen     TIMESTAMPTZ NOT NULL DEFAULT now()
      );

      CREATE TABLE IF NOT EXISTS study.training_progress (
        user_id       TEXT NOT NULL REFERENCES study.users(user_id),
        exam          TEXT NOT NULL CHECK (exam IN ('associate', 'professional')),
        section_id    TEXT NOT NULL,
        visited       BOOLEAN NOT NULL DEFAULT true,
        completed     BOOLEAN NOT NULL DEFAULT false,
        completed_at  TIMESTAMPTZ,
        last_anchor   TEXT,
        scroll_pct    SMALLINT CHECK (scroll_pct BETWEEN 0 AND 100),
        last_seen     TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, section_id)
      );
      CREATE INDEX IF NOT EXISTS ix_training_last_seen
        ON study.training_progress (user_id, exam, last_seen DESC);

      CREATE TABLE IF NOT EXISTS study.review_state (
        user_id        TEXT NOT NULL REFERENCES study.users(user_id),
        question_id    TEXT NOT NULL,
        n              INT NOT NULL DEFAULT 0,
        ease           REAL NOT NULL DEFAULT 2.5,
        due_at         TIMESTAMPTZ,
        last_rated_at  TIMESTAMPTZ,
        last_quality   SMALLINT CHECK (last_quality BETWEEN 0 AND 3),
        right_count    INT NOT NULL DEFAULT 0,
        wrong_count    INT NOT NULL DEFAULT 0,
        PRIMARY KEY (user_id, question_id)
      );

      CREATE TABLE IF NOT EXISTS study.test_attempts (
        attempt_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id             TEXT NOT NULL REFERENCES study.users(user_id),
        exam                TEXT NOT NULL CHECK (exam IN ('associate', 'professional')),
        started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
        time_limit_seconds  INT NOT NULL,
        deadline_at         TIMESTAMPTZ NOT NULL,
        submitted_at        TIMESTAMPTZ,
        auto_submitted      BOOLEAN NOT NULL DEFAULT false,
        question_ids        JSONB NOT NULL,
        answers             JSONB NOT NULL DEFAULT '{}'::jsonb,
        score_correct       INT,
        score_total         INT NOT NULL,
        content_version     TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS ix_attempts_user
        ON study.test_attempts (user_id, exam, started_at DESC);
      CREATE UNIQUE INDEX IF NOT EXISTS ux_one_active_attempt
        ON study.test_attempts (user_id, exam) WHERE submitted_at IS NULL;
    `,
  },
  {
    version: 2,
    name: 'grading_runs',
    sql: `
      CREATE TABLE IF NOT EXISTS study.grading_runs (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id      TEXT NOT NULL REFERENCES study.users(user_id),
        section_id   TEXT NOT NULL,
        run_id       BIGINT,
        status       TEXT NOT NULL CHECK (status IN ('queued', 'running', 'passed', 'failed', 'error')),
        started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        finished_at  TIMESTAMPTZ,
        result       JSONB,
        error        TEXT
      );
      CREATE INDEX IF NOT EXISTS ix_grading_user_section
        ON study.grading_runs (user_id, section_id, started_at DESC);
    `,
  },
  {
    version: 3,
    name: 'visits_and_assignment_copies',
    sql: `
      CREATE TABLE IF NOT EXISTS study.notebook_visits (
        user_id   TEXT NOT NULL REFERENCES study.users(user_id),
        path      TEXT NOT NULL,
        first_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        last_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, path)
      );

      CREATE TABLE IF NOT EXISTS study.assignment_copies (
        user_id        TEXT NOT NULL REFERENCES study.users(user_id),
        section_id     TEXT NOT NULL,
        folder         TEXT NOT NULL,
        notebook       TEXT NOT NULL,
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
        reset_count    INT NOT NULL DEFAULT 0,
        last_reset_at  TIMESTAMPTZ,
        PRIMARY KEY (user_id, section_id)
      );
    `,
  },
];
