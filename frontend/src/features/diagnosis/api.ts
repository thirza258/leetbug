import { useQuery } from '@tanstack/react-query';
import { api, post } from '../../lib/api';
import type { DiagnosisInput, DiagnosisRecord, DiagnosisStatusResponse, ExplanationInput, ExplanationRecord } from './types';

// The hook signature is a fixed contract: Workspace and the assessment/incident runners use it
// to gate "Submit fix" until a diagnosis exists. The API enforces the same rule (HTTP 428).
export interface DiagnosisStatusOptions { enabled: boolean; assessmentSessionId?: string; incidentSessionId?: string }
export interface DiagnosisStatus { required: boolean; submitted: boolean; loading: boolean }
export type SessionOptions = Omit<DiagnosisStatusOptions, 'enabled'>;

export function diagnosisKey(slug: string, options: SessionOptions) {
  return ['diagnosis', slug, options.assessmentSessionId ?? options.incidentSessionId ?? 'practice'] as const;
}

export function sessionFields(options: SessionOptions) {
  return {
    ...(options.assessmentSessionId ? { assessment_session_id: options.assessmentSessionId } : {}),
    ...(options.incidentSessionId ? { incident_session_id: options.incidentSessionId } : {}),
  };
}

function sessionQuery(options: SessionOptions) {
  const params = new URLSearchParams(sessionFields(options));
  return params.size ? `?${params}` : '';
}

const evaluating = (record?: { ai_status: string } | null) => record?.ai_status === 'queued' || record?.ai_status === 'running';

export function useDiagnosisStatusQuery(slug: string, options: DiagnosisStatusOptions) {
  return useQuery({
    queryKey: diagnosisKey(slug, options),
    queryFn: () => api<DiagnosisStatusResponse>(`/problems/${slug}/diagnosis${sessionQuery(options)}`),
    enabled: options.enabled && !!slug,
    // Poll briefly while the optional AI review of the latest record is running.
    refetchInterval: query => query.state.error ? false
      : evaluating(query.state.data?.latest) || evaluating(query.state.data?.explanation) ? 2500 : false,
  });
}

export function useDiagnosisStatus(slug: string, options: DiagnosisStatusOptions): DiagnosisStatus {
  const query = useDiagnosisStatusQuery(slug, options);
  return { required: query.data?.required ?? false, submitted: query.data?.submitted ?? false,
    loading: options.enabled && query.isPending };
}

export function submitDiagnosis(slug: string, input: DiagnosisInput & { language?: string }, options: SessionOptions) {
  return post<DiagnosisRecord>(`/problems/${slug}/diagnosis`, { ...input, ...sessionFields(options) });
}

export function submitExplanation(slug: string, input: ExplanationInput & { submission_id?: string }, options: SessionOptions) {
  return post<ExplanationRecord>(`/problems/${slug}/explanation`, { ...input, ...sessionFields(options) });
}

export const criterionNames: Record<string, string> = {
  defect_category: 'Defect category', root_cause: 'Root cause', invariant: 'Invariant', correction: 'Proposed correction',
  reproduction: 'Reproduction', why_failed: 'Why it failed', why_works: 'Why the fix works',
  side_effects: 'Side effects', additional_tests: 'Additional tests',
};

export const formatScore = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value)}`;
