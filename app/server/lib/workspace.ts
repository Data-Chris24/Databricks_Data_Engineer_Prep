import { createWorkspaceClient } from '@databricks/appkit';
import type { WorkspaceClient } from '@databricks/sdk-experimental';

import type { Starter } from '../../shared/types';

/**
 * Each learner gets their own copy of a section's starter notebooks, in a
 * folder the app's service principal owns and the learner can manage:
 *
 *     <root>/<learner email>/<SECTION>/<starter name>
 *
 * The root defaults to the app service principal's home. The deployed bundle
 * copy is never edited (a redeploy could overwrite it, and the app's principal
 * cannot write there anyway); a reset simply re-imports the starter.
 */
export interface LearnerWorkspace {
  root(): string | null;
  folderFor(userId: string, sectionId: string): string | null;
  provision(userId: string, sectionId: string, starters: Starter[], overwrite: boolean): Promise<{ folder: string; notebook: string }>;
}

function learnerRoot(env: NodeJS.ProcessEnv): string | null {
  const explicit = env.DE_PREP_LEARNER_ROOT?.trim();
  if (explicit) return explicit.replace(/\/+$/, '');
  const sp = env.DATABRICKS_CLIENT_ID?.trim();
  return sp ? `/Users/${sp}/learners` : null;
}

export function createLearnerWorkspace(env: NodeJS.ProcessEnv = process.env): LearnerWorkspace {
  let client: WorkspaceClient | null = null;
  const getClient = () => {
    // AppKit's facade has no Workspace service yet; the underlying SDK client does.
    if (!client) client = createWorkspaceClient().toLegacyWorkspaceClient();
    return client;
  };
  const root = () => learnerRoot(env);

  return {
    root,
    folderFor(userId, sectionId) {
      const r = root();
      return r ? `${r}/${userId}/${sectionId}` : null;
    },
    async provision(userId, sectionId, starters, overwrite) {
      const folder = this.folderFor(userId, sectionId);
      if (!folder) throw new Error('learner workspace root is not configured');
      if (!starters.length) throw new Error(`${sectionId} has no starter notebooks`);
      const ws = getClient();

      await ws.workspace.mkdirs({ path: folder });

      for (const starter of starters) {
        const path = `${folder}/${starter.name}`;
        let exists = false;
        try {
          await ws.workspace.getStatus({ path });
          exists = true;
        } catch {
          exists = false;
        }
        if (exists && !overwrite) continue;
        await ws.workspace.import({
          path,
          format: 'SOURCE',
          language: 'PYTHON',
          overwrite: true,
          content: Buffer.from(starter.source, 'utf8').toString('base64'),
        });
      }

      // The learner manages their own folder; the principal keeps ownership.
      const userFolder = `${root()}/${userId}`;
      const info = await ws.workspace.getStatus({ path: userFolder });
      if (info.object_id !== undefined) {
        await ws.workspace.updatePermissions({
          workspace_object_type: 'directories',
          workspace_object_id: String(info.object_id),
          access_control_list: [{ user_name: userId, permission_level: 'CAN_MANAGE' }],
        });
      }

      const main = starters.find((s) => s.name === 'assignment') ?? starters[0];
      return { folder, notebook: `${folder}/${main.name}` };
    },
  };
}
