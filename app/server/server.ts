import { createApp, jobs, lakebase, server } from '@databricks/appkit';

import { migrate } from './db/migrate';
import type { AppKitLike } from './lib/appkit';
import { userMiddleware } from './lib/http';
import { createLearnerWorkspace } from './lib/workspace';
import { registerAssignmentRoutes } from './routes/assignment';
import { registerConfigRoutes } from './routes/config';
import { registerGradingRoutes } from './routes/grading';
import { registerPracticeRoutes } from './routes/practice';
import { registerTestRoutes } from './routes/tests';
import { registerTrainingRoutes } from './routes/training';

createApp({
  // jobs(): one grading job per section, discovered from DATABRICKS_JOB_GRADE_* env
  // (set by the bundle). With none set the plugin registers nothing and the
  // grading routes answer 503, which the UI turns into the CLI fallback.
  plugins: [lakebase(), jobs(), server()],
  async onPluginsReady(appkit: AppKitLike) {
    try {
      await migrate(appkit.lakebase);
    } catch (err) {
      // Routes still register so the failure is visible in the UI and logs
      // instead of the app refusing to start. The usual cause is the schema
      // being owned by another role - see app/README.md.
      console.error('[db] migration failed:', (err as Error).message);
    }

    appkit.server.extend((app) => {
      app.use('/api', userMiddleware(appkit.lakebase));
      registerConfigRoutes(app, appkit.lakebase);
      registerTrainingRoutes(app, appkit.lakebase);
      registerPracticeRoutes(app, appkit.lakebase);
      registerTestRoutes(app, appkit.lakebase);
      registerGradingRoutes(app, appkit.lakebase, appkit);
      registerAssignmentRoutes(app, appkit.lakebase, createLearnerWorkspace());
    });
  },
}).catch(console.error);
