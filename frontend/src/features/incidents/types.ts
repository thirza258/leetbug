import type { Language, ProblemDetail, Status } from '../../types';

export type Severity = 'SEV-1' | 'SEV-2' | 'SEV-3' | 'SEV-4';
export type ArtifactType = 'logs' | 'metrics' | 'traces' | 'database' | 'config' | 'diff' | 'architecture'
  | 'source' | 'api_contract' | 'runbook';
export type TimelineKind = 'deploy' | 'alert' | 'symptom' | 'action' | 'note';
export interface Label { id: string; name: string }
export interface SessionSummary {
  id: string; status: 'active' | 'resolved' | 'abandoned'; score: number | null; started_at: string; resolved_at: string | null;
}
export interface IncidentListItem {
  slug: string; title: string; summary: string; severity: Severity; level: number; affected_services: string[];
  status: 'published' | 'draft'; category: Label; estimated_minutes: number | null; languages: Language[];
  artifact_count: number; my_session: SessionSummary | null; best_score: number | null;
}
export interface TimelineEntry { at: string; kind: TimelineKind; title: string; detail?: string }
export interface ArtifactManifest { id: string; type: ArtifactType; title: string; description?: string }
export interface Scenario { id: string; name: string; description?: string; tests: string[] }
export interface IncidentOverview {
  slug: string; title: string; summary: string; severity: Severity; level: number; affected_services: string[];
  impact: string[]; expected_behavior: string; observed_symptoms: string[]; status: string; version: number;
  category: Label; timeline: TimelineEntry[]; objective: string; artifacts: ArtifactManifest[]; scenarios: Scenario[];
  weights: Record<string, number>; problem_slug: string; difficulty: string; languages: Language[];
  estimated_minutes: number; my_session?: SessionSummary | null; best_score?: number | null;
}

export interface LogEntry { ts: string; level: string; service: string; message: string; trace_id?: string | null; fields?: Record<string, unknown> }
export interface MetricSeries { name: string; unit?: string; points: [string | number, number][] }
export interface MetricAnnotation { at: string | number; label: string }
export interface Span {
  span_id: string; parent_id?: string | null; service: string; name: string; start_ms: number; duration_ms: number;
  status?: string; attributes?: Record<string, unknown>;
}
export interface Trace { trace_id: string; spans: Span[] }
export interface DataTable { name: string; columns: string[]; rows: unknown[][] }
export interface ArchitectureNode { id: string; label: string; kind?: string }
export interface ArchitectureEdge { from: string; to: string; label?: string }
export interface ArtifactData {
  entries?: LogEntry[]; series?: MetricSeries[]; annotations?: MetricAnnotation[]; traces?: Trace[];
  tables?: DataTable[]; path?: string; language?: string; content?: string; title?: string; author?: string;
  nodes?: ArchitectureNode[]; edges?: ArchitectureEdge[];
}
export interface Artifact extends ArtifactManifest { data: ArtifactData }

export interface RegressionTestInput { name: string; input: unknown; expected: unknown }
export interface RegressionResult {
  name: string; valid: boolean; detects_bug: boolean; reference_status: string | null; starter_status: string | null;
  credit: number; reason: string; your_fix_status?: Status | null;
}
export interface ResolutionScores {
  components: Record<string, number>; total: number | null; weights: Record<string, number>;
  outcome: { fixed_immediate_defect: boolean; prevented_recurrence: boolean; detecting_regression_tests: number };
  details: Record<string, unknown>; best_resolution_id?: string;
}
export interface Resolution {
  id: string; session_id: string; diagnosis_id: string | null; submission_id: string | null;
  impact_assessment: string; remediation: string; prevention: string; regression_tests: RegressionTestInput[];
  regression_results: RegressionResult[]; status: 'queued' | 'running' | 'evaluated' | 'error'; score: number | null;
  scores: Partial<ResolutionScores>; error: string | null; created_at: string; evaluated_at: string | null;
}
export interface Investigation {
  viewed: Record<string, string>; viewed_types: string[]; available_types: string[]; coverage: number;
  runs: number; submissions: number;
}
export interface SessionPayload {
  session: SessionSummary & { scores: Partial<ResolutionScores>; investigation: Investigation };
  incident: Omit<IncidentOverview, 'artifacts'> & { artifacts: Artifact[] };
  problem: ProblemDetail;
  attempt: { id: string; status: string; scores: Record<string, number | null>; total: number | null };
  diagnosis: { required: boolean; submitted: boolean; latest: { id: string; score: number | null; revision: number; created_at: string } | null };
  submissions: { id: string; kind: 'run' | 'submit'; status: Status; language: Language; created_at: string }[];
  resolutions: Resolution[];
}

export interface ValidationCheck { language: string; reference_passed: boolean; starter_compiles: boolean; reproduced_scenarios: string[]; ok: boolean }
export interface AdminIncident extends IncidentOverview {
  id: number; problem_id: number; sessions: number; updated_at: string;
  validation: { status?: 'queued' | 'running' | 'passed' | 'failed' | 'error'; current: boolean; checks?: ValidationCheck[]; error?: string | null; completed_at?: string };
}
