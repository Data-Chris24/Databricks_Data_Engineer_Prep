import type { Application } from 'express';

/**
 * The slice of the AppKit object our routes use. Typed structurally (as the
 * scaffold does) so route modules can be exercised in tests with a fake.
 */
export interface Db {
  query(text: string, params?: unknown[]): Promise<{ rows: Record<string, unknown>[] }>;
}

export interface AppKitLike {
  lakebase: Db;
  server: {
    extend(fn: (app: Application) => void): void;
  };
}
