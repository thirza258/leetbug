import { Component, lazy, StrictMode, Suspense, useEffect } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import '@fontsource/dm-sans/latin-400.css';
import '@fontsource/dm-sans/latin-500.css';
import '@fontsource/dm-sans/latin-600.css';
import '@fontsource/dm-sans/latin-700.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import './styles.css';
import { AuthProvider } from './lib/auth';
import { ThemeProvider, useTheme } from './lib/theme';
import { ApiError } from './lib/api';
import Layout from './components/Layout';
import { EmptyState, Loading } from './components/ui';
import Library from './pages/Library';

const Workspace = lazy(() => import('./pages/Workspace'));
const AuthPage = lazy(() => import('./pages/AuthPage'));
const Progress = lazy(() => import('./pages/Progress'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const Leaderboard = lazy(() => import('./pages/Leaderboard'));
const Discussions = lazy(() => import('./pages/Discussions'));
const NewDiscussion = lazy(() => import('./pages/Discussions').then(module => ({ default: module.NewDiscussion })));
const DiscussionDetail = lazy(() => import('./pages/Discussions').then(module => ({ default: module.DiscussionDetail })));
const Guide = lazy(() => import('./pages/Guide'));
const Courses = lazy(() => import('./pages/Courses'));
const SubmitProblem = lazy(() => import('./pages/SubmitProblem'));
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const IncidentsPage = lazy(() => import('./features/incidents/IncidentsPage'));
const IncidentWorkspace = lazy(() => import('./features/incidents/IncidentWorkspace'));
const AssessmentsPage = lazy(() => import('./features/assessments/AssessmentsPage'));
const AssessmentDetailPage = lazy(() => import('./features/assessments/AssessmentDetailPage'));
const AssessmentRunner = lazy(() => import('./features/assessments/AssessmentRunner'));
const AssessmentReportPage = lazy(() => import('./features/assessments/AssessmentReportPage'));
const AssessmentAdminPage = lazy(() => import('./features/assessments/AssessmentAdminPage'));
const InvitationAcceptPage = lazy(() => import('./features/assessments/InvitationAcceptPage'));
const OrganizationsPage = lazy(() => import('./features/organizations/OrganizationsPage'));
const OrganizationDetailPage = lazy(() => import('./features/organizations/OrganizationDetailPage'));
const QualityAdminPage = lazy(() => import('./features/quality/QualityAdminPage'));
const MetricsAdminPage = lazy(() => import('./features/quality/MetricsAdminPage'));
const RubricAdminPage = lazy(() => import('./features/diagnosis/RubricAdminPage'));
const client = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000,
  retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
  refetchOnWindowFocus: false }, mutations: { retry: false } } });

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}
class ErrorBoundary extends Component<{ children: ReactNode }, { error: boolean }> {
  state = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('Interface error', error, info.componentStack); }
  render() { return this.state.error ? <div className="page"><EmptyState title="The workspace hit a snag."><p>Your saved drafts are still in this browser.</p><button className="button primary" onClick={() => window.location.reload()}>Reload workspace</button></EmptyState></div> : this.props.children; }
}
function App() {
  const { theme } = useTheme();
  return <ErrorBoundary><QueryClientProvider client={client}><BrowserRouter><AuthProvider><ScrollToTop /><Suspense fallback={<Loading />}><Routes>
    <Route path="/login" element={<AuthPage />} /><Route path="/register" element={<AuthPage register />} />
    <Route element={<Layout />}><Route path="/courses/:courseSlug?/:lessonSlug?" element={<Courses />} /></Route>
    <Route element={<Layout />}><Route index element={<Library />} /><Route path="/problems/:slug" element={<Workspace />} /><Route path="/progress" element={<Progress />} /><Route path="/submissions" element={<HistoryPage />} /><Route path="/leaderboard" element={<Leaderboard />} /><Route path="/discussions" element={<Discussions />} /><Route path="/discussions/new" element={<NewDiscussion />} /><Route path="/discussions/:id" element={<DiscussionDetail />} /><Route path="/guide" element={<Guide />} /><Route path="/privacy" element={<LegalPage />} /><Route path="/terms" element={<LegalPage />} /><Route path="/submit-problem" element={<SubmitProblem />} /><Route path="/admin" element={<AdminDashboard />} /><Route path="/incidents" element={<IncidentsPage />} /><Route path="/incidents/:slug" element={<IncidentWorkspace />} /><Route path="/assessments" element={<AssessmentsPage />} /><Route path="/assessments/:slug" element={<AssessmentDetailPage />} /><Route path="/assessment-sessions/:id" element={<AssessmentRunner />} /><Route path="/assessment-sessions/:id/report" element={<AssessmentReportPage />} /><Route path="/assessment-invitations/:token" element={<InvitationAcceptPage />} /><Route path="/organizations" element={<OrganizationsPage />} /><Route path="/organizations/:slug" element={<OrganizationDetailPage />} /><Route path="/admin/quality" element={<QualityAdminPage />} /><Route path="/admin/metrics" element={<MetricsAdminPage />} /><Route path="/admin/assessments" element={<AssessmentAdminPage />} /><Route path="/admin/rubrics" element={<RubricAdminPage />} /><Route path="*" element={<div className="page"><EmptyState title="This page wandered off."><p>There are plenty of bugs waiting back in the library.</p><Link to="/" className="button primary">Back to library</Link></EmptyState></div>} /></Route>
  </Routes></Suspense><Toaster theme={theme} position="bottom-right" closeButton /></AuthProvider></BrowserRouter></QueryClientProvider></ErrorBoundary>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><ThemeProvider><App /></ThemeProvider></StrictMode>);
