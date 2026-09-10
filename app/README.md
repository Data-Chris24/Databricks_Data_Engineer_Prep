# de-prep-study

The study app: **Learn** (section notes with a table of contents, links into the
lesson notebooks and the graded assignment, progress that resumes where you left
off) and **Test** (practice with instant feedback and spaced repetition, and timed
tests at the real exam's length). Built with
[AppKit](https://developers.databricks.com/docs/appkit/v0/) (TypeScript, React,
Express) and Lakebase Postgres for per-user progress.

Content is not stored here. `tools/build_app_content.py` renders the objective
maps, question bank, lesson notes and notebook index from `content/` and
`notebooks/` into `shared/content/*.json`, which is committed and imported at
build time. Edit the YAML or markdown, re-run the script, commit the JSON; CI
fails if the JSON is stale.

## How it is deployed

Only by CI, from `main`, through the repo bundle
(`bundle/resources/de_prep_study_app.app.yml`). Do not `databricks bundle deploy`
from a laptop: development mode would create a second, dev-prefixed app and Free
Edition allows three.

The Lakebase project (`projects/de-prep`) was created once by hand and is not a
bundle resource, so no bundle command can delete learner progress.

## Local development

**Deploy before you develop.** The app's service principal must be the role that
creates the `study` schema on first start, otherwise the deployed app can never
access it (Postgres schema ownership follows the creating role). Check before
running anything locally:

```bash
databricks apps get de-prep-study --profile FREE -o json | jq '.active_deployment.status.state'
# must be SUCCEEDED before the steps below
```

Then:

```bash
npm install
cp .env.example .env        # fill in the values below
npm run dev                 # http://localhost:8000, hot reload for UI and server
```

`.env` (never committed):

```dotenv
DATABRICKS_CONFIG_PROFILE=FREE
DATABRICKS_APP_NAME=de-prep-study
DATABRICKS_APP_PORT=8000
LAKEBASE_ENDPOINT=projects/de-prep/branches/production/endpoints/primary
PGHOST=<host from: databricks postgres get-endpoint projects/de-prep/branches/production/endpoints/primary --profile FREE>
PGPORT=5432
PGDATABASE=databricks_postgres
PGSSLMODE=require
DEV_USER_EMAIL=you@example.com   # stands in for the identity header the platform adds
```

To run the UI with no server and no database at all:

```bash
VITE_STORE=memory npm run dev
```

## Checks

```bash
npm run typecheck
npm run lint
npm test
npm run build
databricks apps validate --profile FREE    # all of the above, the way the platform runs them
```

## Layout

```
shared/content/     generated JSON (exams, questions, notes, notebooks, meta)
shared/             types, SM-2 scheduling, test sampler, grader - used by both sides
server/db/          migrations, applied idempotently at startup
server/routes/      /api/me, /api/config, /api/training, /api/practice, /api/tests
client/src/lib/     StudyStore (ApiStore | MemoryStore), markdown renderer, timer
client/src/pages/   Home, train/*, test/*
```
