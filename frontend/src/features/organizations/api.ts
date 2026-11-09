import { api, post } from '../../lib/api';
import type { Analytics, CandidateRow, Comparison, CompetencyProfile, Member, OrgAssessment, OrgInvitation, OrgRole, Organization, Taxonomy } from './types';

interface List<T> { items: T[]; total: number }
const base = (slug: string) => `/organizations/${encodeURIComponent(slug)}`;
const send = <T,>(path: string, method: 'PATCH' | 'DELETE', body?: unknown) =>
  api<T>(path, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export const listOrganizations = () => api<List<Organization>>('/organizations');
export const createOrganization = (name: string, slug?: string) => post<Organization>('/organizations', slug ? { name, slug } : { name });
export const getOrganization = (slug: string) => api<Organization>(base(slug));
export const renameOrganization = (slug: string, name: string) => send<Organization>(base(slug), 'PATCH', { name });

export const listMembers = (slug: string) => api<List<Member>>(`${base(slug)}/members`);
export const addMember = (slug: string, email: string, role: OrgRole) => post<Member>(`${base(slug)}/members`, { email, role });
export const changeRole = (slug: string, userId: string, role: OrgRole) => send<{ user_id: string; role: OrgRole }>(`${base(slug)}/members/${userId}`, 'PATCH', { role });
export const removeMember = (slug: string, userId: string) => send<void>(`${base(slug)}/members/${userId}`, 'DELETE');

export const listOrgAssessments = (slug: string) => api<List<OrgAssessment>>(`${base(slug)}/assessments`);
export const createOrgAssessment = (slug: string, body: unknown) => post<OrgAssessment>(`${base(slug)}/assessments`, body);
export const setExpiration = (slug: string, id: string, available_until: string | null) => send<OrgAssessment>(`${base(slug)}/assessments/${id}/expiration`, 'PATCH', { available_until });
export const exportUrl = (slug: string, id: string, format: 'csv' | 'json') => `/api${base(slug)}/assessments/${id}/export?format=${format}`;

export const listInvitations = (slug: string) => api<List<OrgInvitation> & { status_counts: Record<string, number> }>(`${base(slug)}/invitations`);
export const extendInvitation = (slug: string, id: string, extend_days: number) => send<OrgInvitation>(`${base(slug)}/invitations/${id}`, 'PATCH', { extend_days });
export const revokeInvitation = (slug: string, id: string) => send<void>(`${base(slug)}/invitations/${id}`, 'DELETE');

export const listCandidates = (slug: string, assessmentId = '') => api<List<CandidateRow> & { notes: string[] }>(`${base(slug)}/candidates${assessmentId ? `?assessment_id=${assessmentId}` : ''}`);
export const getAnalytics = (slug: string, assessmentId = '') => api<Analytics>(`${base(slug)}/analytics${assessmentId ? `?assessment_id=${assessmentId}` : ''}`);
export const compareSessions = (slug: string, ids: string[]) => api<Comparison>(`${base(slug)}/compare?sessions=${ids.map(encodeURIComponent).join(',')}`);

export const listProfiles = (slug: string) => api<List<CompetencyProfile>>(`${base(slug)}/competency-profiles`);
export const createProfile = (slug: string, body: unknown) => post<CompetencyProfile>(`${base(slug)}/competency-profiles`, body);
export const updateProfile = (slug: string, id: string, body: unknown) => send<CompetencyProfile>(`${base(slug)}/competency-profiles/${id}`, 'PATCH', body);
export const deleteProfile = (slug: string, id: string) => send<void>(`${base(slug)}/competency-profiles/${id}`, 'DELETE');
export const availableProfiles = (organizationId?: string | null) => api<List<CompetencyProfile>>(`/competency-profiles${organizationId ? `?organization_id=${organizationId}` : ''}`);
export const getTaxonomy = () => api<Taxonomy>('/taxonomy');
