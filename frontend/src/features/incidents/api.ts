import { api, post } from '../../lib/api';
import type { IncidentListItem, IncidentOverview, Resolution, RegressionTestInput, SessionPayload } from './types';

export const incidentKeys = {
  list: (userId?: string) => ['incidents', userId] as const,
  overview: (slug: string, userId?: string) => ['incident', slug, userId] as const,
  session: (id?: string) => ['incident-session', id] as const,
};
export const listIncidents = () => api<{ items: IncidentListItem[] }>('/incidents');
export const getIncident = (slug: string) => api<IncidentOverview>(`/incidents/${slug}`);
export const startSession = (slug: string) => post<SessionPayload>(`/incidents/${slug}/sessions`);
export const getSession = (id: string) => api<SessionPayload>(`/incidents/sessions/${id}`);
export const recordView = (sessionId: string, artifactId: string) =>
  post<{ artifact_id: string; first_view: boolean }>(`/incidents/sessions/${sessionId}/artifacts/${encodeURIComponent(artifactId)}/view`);
export interface ResolutionInput {
  impact_assessment: string; remediation: string; prevention: string; regression_tests: RegressionTestInput[];
  submission_id?: string;
}
export const resolve = (sessionId: string, body: ResolutionInput) => post<Resolution>(`/incidents/sessions/${sessionId}/resolve`, body);
export const retryResolution = (id: string) => post<Resolution>(`/incidents/resolutions/${id}/retry`);

export const adminIncidents = () => api<{ items: import('./types').AdminIncident[] }>('/admin/incidents');
export const adminCreate = (definition: unknown) => post<import('./types').AdminIncident>('/admin/incidents', definition);
export const adminAction = (slug: string, action: 'validate' | 'publish' | 'unpublish') =>
  post<import('./types').AdminIncident>(`/admin/incidents/${slug}/${action}`);
