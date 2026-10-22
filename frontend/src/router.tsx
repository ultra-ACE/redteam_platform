import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { ModelsPage } from './pages/ModelsPage';
import { BenchmarksPage } from './pages/BenchmarksPage';
import { TasksPage } from './pages/TasksPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { ResultsPage } from './pages/ResultsPage';
import { StatisticsPage } from './pages/StatisticsPage';
import { ReportsPage } from './pages/ReportsPage';
import { JudgePage } from './pages/JudgePage';
import { ReviewsPage } from './pages/ReviewsPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/tasks" replace /> },
      { path: 'statistics', element: <StatisticsPage /> },
      { path: 'models', element: <ModelsPage /> },
      { path: 'benchmarks', element: <BenchmarksPage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'tasks/:taskId', element: <TaskDetailPage /> },
      { path: 'results', element: <ResultsPage /> },
      { path: 'reviews', element: <ReviewsPage /> },
      { path: 'judge', element: <JudgePage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'files', element: <Navigate to="/reports" replace /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);
