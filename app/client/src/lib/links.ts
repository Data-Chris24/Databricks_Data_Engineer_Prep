import type { AppConfig } from '../../../shared/types';

/**
 * Deep link to a repo file as deployed by the bundle. The bundle lands files
 * under `<filesRoot>` (the bundle's workspace.file_path), and the workspace UI
 * opens any path with the `#workspace` fragment.
 */
export function workspaceUrl(config: AppConfig | null, repoPath: string): string | null {
  if (!config?.workspaceHost || !config.filesRoot) return null;
  const root = config.filesRoot.replace(/\/+$/, '');
  return `${config.workspaceHost}/#workspace${root}/${repoPath}`;
}
