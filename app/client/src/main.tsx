import { ResourceStatusIndicator, ResourceStatusProvider } from '@databricks/appkit-ui/react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import './index.css';
import App from './App.tsx';
import { ErrorBoundary } from './ErrorBoundary.tsx';
import { ExamProvider } from './lib/exam.tsx';
import { ApiStore, MemoryStore, StoreContext } from './lib/store.ts';

// VITE_STORE=memory runs the whole UI without a server or database.
const store = import.meta.env.VITE_STORE === 'memory' ? new MemoryStore() : new ApiStore();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ResourceStatusProvider>
        <ResourceStatusIndicator />
        <StoreContext.Provider value={store}>
          <ExamProvider>
            <App />
          </ExamProvider>
        </StoreContext.Provider>
      </ResourceStatusProvider>
    </ErrorBoundary>
  </StrictMode>,
);
