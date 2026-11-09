import { api, post } from '../../lib/api';
import type {
  AdminAssessment, AdminSession, AssessmentCard, AssessmentDetail, AssessmentReport, AssessmentSessionView,
  CreatedInvitation, Invitation, MySession,
} from './types';

interface List<T> { items: T[]; total: number }
const json = (body: unknown) => ({ body: JSON.stringify(body) });

export const listAssessments = () => api<List<AssessmentCard>>('/assessments');
export const getAssessment = (slug: string) => api<AssessmentDetail>(`/assessments/${encodeURIComponent(slug)}`);
export const startAssessment = (slug: string) => post<AssessmentSessionView>(`/assessments/${encodeURIComponent(slug)}/sessions`);
export const mySessions = () => api<List<MySession>>('/me/assessment-sessions');
export const getSession = (id: string) => api<AssessmentSessionView>(`/assessment-sessions/${id}`);
export const finishSession = (id: string) => post<AssessmentSessionView>(`/assessment-sessions/${id}/submit`);
export const getReport = (id: string) => api<AssessmentReport>(`/assessment-sessions/${id}/report`);
export const exportUrl = (id: string, format: 'json' | 'csv' | 'md') => `/api/assessment-sessions/${id}/report/export?format=${format}`;
export const acceptInvitation = (token: string) => post<{ assessment: AssessmentCard; invitation: { id: string; status: string; email: string } }>('/assessment-invitations/accept', { token });

export const adminAssessments = () => api<List<AdminAssessment>>('/admin/assessments');
export const createAssessment = (body: unknown) => post<AdminAssessment>('/admin/assessments', body);
export const updateAssessment = (id: string, body: unknown) => api<AdminAssessment>(`/admin/assessments/${id}`, { method: 'PATCH', ...json(body) });
export const publishAssessment = (id: string) => post<AdminAssessment>(`/admin/assessments/${id}/publish`);
export const archiveAssessment = (id: string) => post<AdminAssessment>(`/admin/assessments/${id}/archive`);
export const adminSessions = (id: string) => api<List<AdminSession>>(`/admin/assessments/${id}/sessions`);
export const adminInvitations = (id: string) => api<List<Invitation>>(`/admin/assessments/${id}/invitations`);
export const createInvitations = (id: string, emails: string[], expires_in_days: number) => post<{ items: CreatedInvitation[] }>(`/admin/assessments/${id}/invitations`, { emails, expires_in_days });
export const revokeInvitation = (id: string) => api<void>(`/admin/assessment-invitations/${id}`, { method: 'DELETE' });
export const correctSession = (id: string, body: unknown) => post<{ report_version: number; total_score: number }>(`/admin/assessment-sessions/${id}/corrections`, body);
export const releaseSession = (id: string) => post<{ released: boolean }>(`/admin/assessment-sessions/${id}/release`);
