import { lazy } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import AppLayout from './components/AppLayout.jsx';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import { useAuth } from './context/contexts.js';
import LoginPage from './pages/LoginPage.jsx';

// Pages are downloaded when they are first opened.
const AdminPage = lazy(() => import('./pages/AdminPage.jsx'));
const BudgetsPage = lazy(() => import('./pages/BudgetsPage.jsx'));
const DashboardPage = lazy(() => import('./pages/DashboardPage.jsx'));
const DeliverableDetailsPage = lazy(() => import('./pages/DeliverableDetailsPage.jsx'));
const DeliverableFormPage = lazy(() => import('./pages/DeliverableFormPage.jsx'));
const DeliverablesPage = lazy(() => import('./pages/DeliverablesPage.jsx'));
const ExpensesPage = lazy(() => import('./pages/ExpensesPage.jsx'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage.jsx'));
const ProjectDetailsPage = lazy(() => import('./pages/ProjectDetailsPage.jsx'));
const ProjectFormPage = lazy(() => import('./pages/ProjectFormPage.jsx'));
const ProjectsPage = lazy(() => import('./pages/ProjectsPage.jsx'));
const ResourceDetailsPage = lazy(() => import('./pages/ResourceDetailsPage.jsx'));
const ResourceFormPage = lazy(() => import('./pages/ResourceFormPage.jsx'));
const ResourcesPage = lazy(() => import('./pages/ResourcesPage.jsx'));
const WorkloadPage = lazy(() => import('./pages/WorkloadPage.jsx'));

/**
 * Opens the first page a user may see.
 * @returns {JSX.Element} A redirect.
 */
function HomePage() {
  const { can } = useAuth();
  return <Navigate to={can('reports:view') ? '/dashboard' : '/projects'} replace />;
}

const guard = (permission, page) => (
  <ProtectedRoute permission={permission}>{page}</ProtectedRoute>
);

/**
 * Defines the pages of the application.
 * @returns {JSX.Element} The routes.
 */
function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={(
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        )}
      >
        <Route index element={<HomePage />} />
        <Route path="/dashboard" element={guard('reports:view', <DashboardPage />)} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route
          path="/projects/new"
          element={guard('projects:create', <ProjectFormPage key="new" />)}
        />
        <Route path="/projects/:projectId" element={<ProjectDetailsPage />} />
        <Route
          path="/projects/:projectId/edit"
          element={<ProjectFormPage key="edit" />}
        />
        <Route
          path="/projects/:projectId/deliverables/new"
          element={<DeliverableFormPage key="new" />}
        />
        <Route path="/deliverables" element={<DeliverablesPage />} />
        <Route path="/deliverables/:deliverableId" element={<DeliverableDetailsPage />} />
        <Route
          path="/deliverables/:deliverableId/edit"
          element={<DeliverableFormPage key="edit" />}
        />
        <Route path="/resources" element={guard('resources:view', <ResourcesPage />)} />
        <Route
          path="/resources/new"
          element={guard('resources:manage', <ResourceFormPage key="new" />)}
        />
        <Route
          path="/resources/:resourceId"
          element={guard('resources:view', <ResourceDetailsPage />)}
        />
        <Route
          path="/resources/:resourceId/edit"
          element={guard('resources:manage', <ResourceFormPage key="edit" />)}
        />
        <Route path="/budgets" element={guard('budgets:manage', <BudgetsPage />)} />
        <Route path="/expenses" element={guard('budgets:manage', <ExpensesPage />)} />
        <Route
          path="/admin/:section?"
          element={guard('users:manage', <AdminPage />)}
        />
        <Route path="/workload" element={guard('reports:view', <WorkloadPage />)} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export default App;
