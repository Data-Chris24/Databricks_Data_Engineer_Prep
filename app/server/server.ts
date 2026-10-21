import { createApp, jobs, lakebase, server } from '@databricks/appkit';

import { migrate } from './db/migrate';
import { bootstrapEnv } from './lib/bootstrap';
import type { AppKitLike } from './lib/appkit';
import { sendIfAsleep, userMiddleware } from './lib/http';
import { createWaker, wakingDb } from './lib/wake';
import { createLearnerWorkspace } from './lib/workspace';
import { registerAssignmentRoutes } from './routes/assignment';
import { registerConfigRoutes } from './routes/config';
import { registerDatasetRoutes } from './routes/datasets';
import { registerGradingRoutes } from './routes/grading';
import { registerPracticeRoutes } from './routes/practice';
import { registerTestRoutes } from './routes/tests';
import { registerTrainingRoutes } from './routes/training';

// A deployment started from the Apps UI (or `apps deploy`) has app.yaml's
// environment only; the job ids and files root the bundle would have passed are
// recovered by name first. See lib/bootstrap.ts.
await bootstrapEnv();

createApp({
  // jobs(): every job the app runs, from the DATABRICKS_JOB_* variables
  // bootstrapEnv resolved above. With none set the plugin refuses to start, so
  // bootstrapEnv also sets DATABRICKS_JOB_ID.
  plugins: [lakebase(), jobs(), server()],
  async onPluginsReady(appkit: AppKitLike) {
    // Every query goes through wakingDb: if Free Edition has disabled the
    // Lakebase endpoint, the first failing query starts the wake job and the
    // learner gets "waking up" instead of a server error. See lib/wake.ts.
    const db = wakingDb(
      appkit.lakebase,
      createWaker(() => {
        try {
          return appkit.jobs ? appkit.jobs('wake_database') : null;
        } catch {
          return null;
        }
      }),
    );

    // Migrations run at startup, and again on a later request if that failed:
    // an app started while the endpoint was disabled must not stay unmigrated
    // once it wakes. One attempt at a time, and at most one a minute.
    let migrated = false;
    let migrating: Promise<void> | null = null;
    let lastTry = 0;
    const ensureMigrated = () => {
      lastTry = Date.now();
      return (migrating ??= migrate(db)
        .then(() => {
          migrated = true;
        })
        .finally(() => {
          migrating = null;
        }));
    };
    try {
      await ensureMigrated();
    } catch (err) {
      // Routes still register so the failure is visible in the UI and logs
      // instead of the app refusing to start. Besides a disabled endpoint, the
      // usual cause is the schema being owned by another role - see app/README.md.
      console.error('[db] migration failed:', (err as Error).message);
    }

    appkit.server.extend((app) => {
      app.use('/api', (_req, res, next) => {
        if (migrated || (!migrating && Date.now() - lastTry < 60_000)) return next();
        ensureMigrated().then(
          () => next(),
          (err: unknown) => {
            // Asleep: answer 503 so the client waits. Anything else: log it and
            // let the route try, as before this retry existed.
            if (sendIfAsleep(res, err)) return;
            console.error('[db] migration failed:', (err as Error).message);
            next();
          },
        );
      });
      app.use('/api', userMiddleware(db));
      registerConfigRoutes(app, db);
      registerDatasetRoutes(app, db, appkit);
      registerTrainingRoutes(app, db);
      registerPracticeRoutes(app, db);
      registerTestRoutes(app, db);
      registerGradingRoutes(app, db, appkit);
      registerAssignmentRoutes(app, db, createLearnerWorkspace(), appkit);
    });
  },
}).catch(console.error);
