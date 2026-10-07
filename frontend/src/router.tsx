import { createBrowserRouter } from 'react-router-dom';
import { AppLayout } from './layouts/AppLayout';
import { DashboardPage } from './pages/DashboardPage';
import { ModelsPage } from './pages/ModelsPage';
import { BenchmarksPage } from './pages/BenchmarksPage';
import { TasksPage } from './pages/TasksPage';
import { TaskDetailPage } from './pages/TaskDetailPage';
import { ResultsPage } from './pages/ResultsPage';
import { StatisticsPage } from './pages/StatisticsPage';
import { ReportsPage } from './pages/ReportsPage';
import { ReportTemplatesPage } from './pages/ReportTemplatesPage';
import { RiskTaxonomyPage } from './pages/RiskTaxonomyPage';
import { AttackTemplatesPage } from './pages/AttackTemplatesPage';
import { JudgePage } from './pages/JudgePage';
import { ReviewsPage } from './pages/ReviewsPage';
import { SystemPage } from './pages/SystemPage';
import { AuditPage } from './pages/AuditPage';
import { FilesPage } from './pages/FilesPage';
import { NotFoundPage } from './pages/NotFoundPage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'statistics', element: <StatisticsPage /> },
      { path: 'models', element: <ModelsPage /> },
      { path: 'benchmarks', element: <BenchmarksPage /> },
      { path: 'attack-templates', element: <AttackTemplatesPage /> },
      { path: 'risk-taxonomy', element: <RiskTaxonomyPage /> },
      { path: 'tasks', element: <TasksPage /> },
      { path: 'tasks/:taskId', element: <TaskDetailPage /> },
      { path: 'results', element: <ResultsPage /> },
      { path: 'reviews', element: <ReviewsPage /> },
      { path: 'judge', element: <JudgePage /> },
      { path: 'reports', element: <ReportsPage /> },
      { path: 'report-templates', element: <ReportTemplatesPage /> },
      { path: 'system', element: <SystemPage /> },
      { path: 'audit', element: <AuditPage /> },
      { path: 'files', element: <FilesPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

