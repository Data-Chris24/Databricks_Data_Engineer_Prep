import { useEffect, useRef } from 'react';
import { createBrowserRouter, Link, NavLink, Outlet, RouterProvider, useLocation, useParams } from 'react-router';

import { isExamId } from '../../shared/content';
import { ExamSwitch } from './components/ExamSwitch';
import { Icon } from './components/Icon';
import { useExam } from './lib/exam';
import { useStore } from './lib/store';
import { Home } from './pages/Home';
import { Practice } from './pages/test/Practice';
import { Review } from './pages/test/Review';
import { Score } from './pages/test/Score';
import { TestingHome } from './pages/test/TestingHome';
import { TestRun } from './pages/test/TestRun';
import { TestSetup } from './pages/test/TestSetup';
import { SectionPage } from './pages/train/SectionPage';
import { TrainingHome } from './pages/train/TrainingHome';

function Shell() {
  const { examId, setExamId } = useExam();
  const params = useParams();
  const location = useLocation();
  const store = useStore();
  const lastArea = useRef<string | null>(null);

  // The URL is the source of truth for the exam; keep the switch in step.
  useEffect(() => {
    if (params.exam && isExamId(params.exam) && params.exam !== examId) setExamId(params.exam);
  }, [params.exam, examId, setExamId]);

  // Remember which area the learner was in, so the home page can offer to continue it.
  useEffect(() => {
    const area = location.pathname.startsWith('/train') ? 'learn' : 'test';
    if (lastArea.current === area) return;
    lastArea.current = area;
    store.setLastArea(area).catch(() => {});
  }, [location.pathname, store]);

  return (
    <>
      <header className="shell-header">
        <div className="header-group">
          <Link to="/" className="brand">
            <span className="brand-mark">
              <Icon name="layers" size={16} stroke={2} />
            </span>
            Databricks DE Prep
          </Link>
          <nav className="seg" aria-label="Area">
            <NavLink to={`/train/${examId}`}>Learn</NavLink>
            <NavLink to={`/test/${examId}`}>Test</NavLink>
          </nav>
        </div>
        <ExamSwitch />
      </header>
      <Outlet />
    </>
  );
}

const router = createBrowserRouter([
  { path: '/', element: <Home /> },
  {
    element: <Shell />,
    children: [
      { path: '/train/:exam', element: <TrainingHome /> },
      { path: '/train/:exam/:sectionId', element: <SectionPage /> },
      { path: '/test/:exam', element: <TestingHome /> },
      { path: '/test/:exam/practice', element: <Practice /> },
      { path: '/test/:exam/exam', element: <TestSetup /> },
      { path: '/test/attempt/:id', element: <TestRun /> },
      { path: '/test/attempt/:id/score', element: <Score /> },
      { path: '/test/attempt/:id/review', element: <Review /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
