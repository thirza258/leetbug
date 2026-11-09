export type GateStatus = 'approved' | 'requires_revision';
export type QualityStatus = GateStatus | 'unvalidated';
export type RunStatus = 'queued' | 'validating' | 'running' | 'completed' | 'failed';
export type CaseStatus = 'queued' | 'running' | 'killed' | 'survived' | 'timeout' | 'invalid' | 'equivalent' | 'error';

export interface PipelineStep { step: string; status: 'passed' | 'failed' | 'warning' | 'skipped' | 'running'; detail: string; data?: Record<string, unknown> }
export interface GateCheck { name: string; passed: boolean; detail: string; required: boolean }
export interface MutationSummary {
  total: number; killed: number; timed_out: number; survived: number; invalid: number; equivalent: number; errors: number;
  pending: number; scored: number; detected: number; score: number | null; count_timeouts_as_killed: boolean;
  critical_total: number; critical_scored: number; critical_killed: number; critical_survived: number;
  by_operator: Record<string, Record<string, number>>;
}
export interface QualityReport {
  problem?: { slug: string; title: string; version: number | null; content_hash: string };
  language?: string; pipeline?: PipelineStep[]; mutation?: MutationSummary;
  tests?: { total: number; public: number; hidden: number; with_state_assertions: number;
    edge_case_coverage: { present: string[]; count: number; total: number }; concurrency_probes: number | null;
    meaningful_hidden_tests: string[]; per_test_kills: Record<string, number> };
  reference?: { passed: boolean; stable: boolean; max_case_runtime_ms: number | null; runs: number };
  starter?: { compiled: boolean; status: string; public_failures: string[]; hidden_failures: string[] };
  leakage?: { findings: { source: string; kind: string; severity: 'error' | 'warning'; excerpt: string }[] };
  gate?: { status: GateStatus; reasons: string[]; checks: GateCheck[]; thresholds: Thresholds };
  generated_at?: string;
}
export interface MutationRun {
  id: string; problem_id: number; problem_slug?: string; problem_title?: string; current_version?: number;
  problem_version: number; content_hash: string; language: string; status: RunStatus;
  config: { max_mutants: number; operators: string[] | null; thresholds?: Thresholds };
  total_mutations: number; killed_mutations: number; survived_mutations: number; timed_out_mutations: number;
  invalid_mutations: number; equivalent_mutations: number; error_mutations: number; mutation_score: number | null;
  gate_status: GateStatus | null; error: string | null; created_at: string; started_at: string | null;
  completed_at: string | null; report?: QualityReport; pipeline?: PipelineStep[];
}
export interface MutationCase {
  id: string; run_id: string; ordinal: number; operator: string; operator_label: string; description: string;
  line: number | null; critical: boolean; original_snippet: string; mutated_snippet: string; status: CaseStatus;
  failure_classification: string | null; killing_tests: { name: string; hidden: boolean; status: string }[];
  is_equivalent: boolean; attempts: number; execution_duration_ms: number | null; note: string; message: string | null;
}
export interface OverviewRow {
  id: number; slug: string; title: string; category: string; difficulty: string; visibility: string; version: number;
  languages: string[]; quality_status: QualityStatus; stale: boolean; source: string;
  latest_run: { id: string; status: RunStatus; language: string; mutation_score: number | null; gate_status: GateStatus | null;
    problem_version: number; created_at: string; completed_at: string | null } | null;
}
export interface Overview {
  items: OverviewRow[]; total: number; page: number; limit: number; categories: string[];
  summary: { approved: number; requires_revision: number; unvalidated: number; validated_problems: number;
    published_new: number; published_new_approved_rate: number | null };
}
export type Thresholds = Record<string, number | boolean>;
export interface GateConfig {
  defaults: Thresholds; schema: Record<string, { type: 'float' | 'int' | 'bool'; min: number | null; max: number | null }>;
  overrides: { category: string; thresholds: Thresholds; updated_at: string; updated_by: string | null }[];
  effective: Record<string, Thresholds>; categories: string[];
}
export interface CommunityItem {
  id: string; title: string; author_username: string; language: string; category: string; created_at: string;
  test_case_count: number; problem: { id: number; slug: string; visibility: string; quality_status: QualityStatus; version: number } | null;
}
export interface Percentiles { samples: number; p50: number | null; p95: number | null; p99: number | null }
export interface AdminMetrics {
  generated_at: string; window_days: number;
  health: { database: string; redis: string }; queues: Record<string, number | null>;
  jobs_in_progress: Record<string, number>;
  execution: { evaluations: number; service_errors: number; service_error_rate: number | null; runtime_ms: Percentiles;
    turnaround_ms: Percentiles; by_language: Record<string, { runtime_ms: Percentiles; turnaround_ms: Percentiles }> };
  mutation: { cases: number; infrastructure_error_rate: number | null; invalid_rate: number | null; timeout_rate: number | null;
    equivalent_rate: number | null; case_duration_ms: Percentiles; runs: Record<string, number>; approved_runs: number;
    validation_duration_ms: Percentiles };
  ai: { interactions: number; error_rate: number | null; retrieval_ms: Percentiles; generation_ms: Percentiles; latency_ms: Percentiles };
  ai_evaluation: { failure_rate: number | null; diagnoses: { completed: number; failed: number; failure_rate: number | null };
    explanations: { completed: number; failed: number; failure_rate: number | null } };
  assessments: { finalized: number; finalization_latency_ms: Percentiles };
  sandbox: { orphaned_containers: number | null; observed_at: string | null; note: string };
}
export interface CalibrationItem {
  problem_id: number; slug: string; title: string; category: string; difficulty: string; estimated_minutes: number;
  samples: number; solved: number; solve_rate: number | null; median_solve_seconds: number | null; avg_submissions: number | null;
  diagnosis_accuracy: number | null; hint_usage_rate: number | null; abandonment_rate: number | null;
  hidden_failure_rate: number | null; ai_dependency_rate: number | null; confidence: string;
  cohorts: Record<string, { samples: number; solve_rate: number | null }>;
  suggestion: { difficulty: string; direction: 'easier' | 'harder' | 'consistent'; reason: string; applied: false } | null;
}
export interface Calibration { items: CalibrationItem[]; total: number; page: number; limit: number; min_samples: number; pages: number; note: string }
