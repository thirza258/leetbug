import { api, post } from '../../lib/api';
import type { AdminMetrics, Calibration, CommunityItem, GateConfig, MutationCase, MutationRun, Overview, Thresholds } from './types';

const json = (method: string, body?: unknown): RequestInit => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export const qualityApi = {
  overview: (params: URLSearchParams) => api<Overview>(`/admin/quality/overview?${params}`),
  runs: (slug: string) => api<{ problem: { id: number; slug: string; title: string; version: number; visibility: string; quality_status: string; languages: string[]; source: string }; items: MutationRun[] }>(`/admin/problems/${slug}/mutation-runs`),
  history: (slug: string) => api<{ current_version: number; versions: { version: number; runs: { run_id: string; language: string; mutation_score: number | null; gate_status: string | null; completed_at: string | null }[] }[] }>(`/admin/problems/${slug}/quality-history`),
  startRun: (slug: string, body: { language?: string; max_mutants: number; operators?: string[] }) => post<MutationRun>(`/admin/problems/${slug}/mutation-runs`, body),
  run: (id: string) => api<MutationRun>(`/admin/mutation-runs/${id}`),
  cases: (id: string, status = '') => api<{ items: MutationCase[] }>(`/admin/mutation-runs/${id}/cases${status === 'critical' ? '?critical=true' : status ? `?status=${status}` : ''}`),
  markEquivalent: (id: string, is_equivalent: boolean, note: string) => api<{ case: MutationCase; run: MutationRun }>(`/admin/mutation-cases/${id}`, json('PATCH', { is_equivalent, note })),
  gates: () => api<GateConfig>('/admin/quality-gates'),
  saveGate: (category: string, thresholds: Thresholds) => api<{ category: string; thresholds: Thresholds }>(`/admin/quality-gates/${category}`, json('PUT', { thresholds })),
  resetGate: (category: string) => api<void>(`/admin/quality-gates/${category}`, json('DELETE')),
  operators: () => api<{ operators: { id: string; label: string }[] }>('/admin/quality/operators'),
  community: () => api<{ items: CommunityItem[] }>('/admin/quality/community'),
  createDraft: (submissionId: string) => post<{ id: number; slug: string }>(`/admin/problem-submissions/${submissionId}/draft`),
  publish: (slug: string) => post<{ visibility: string }>(`/admin/problems/${slug}/publish`),
  unpublish: (slug: string) => post<{ visibility: string }>(`/admin/problems/${slug}/unpublish`),
  metrics: (days: number) => api<AdminMetrics>(`/admin/metrics?days=${days}`),
  calibration: (minSamples: number, page: number) => api<Calibration>(`/admin/calibration?min_samples=${minSamples}&page=${page}`),
};

export const activeRun = (status?: string) => status === 'queued' || status === 'validating' || status === 'running';
export const label = (value: string) => value.replaceAll('_', ' ');
