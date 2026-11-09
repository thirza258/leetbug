import type { Language } from '../../types';

export type CriterionLevel = 'strong' | 'partial' | 'missing';
export type AiStatus = 'skipped' | 'queued' | 'running' | 'completed' | 'failed';
export type AttemptContext = 'practice' | 'incident' | 'assessment';
export interface Criterion { score: number; level: CriterionLevel; feedback: string; weight: number }
export interface BugCategory { id: string; name: string; description: string }

export interface DiagnosisInput {
  defect_category: string; root_cause: string; affected_component: string;
  violated_invariant: string; proposed_correction: string; reproduction_strategy: string;
}
export interface DiagnosisRecord extends DiagnosisInput {
  id: string; problem_id: number; attempt_id: string; assessment_session_id: string | null; revision: number;
  language: Language | null; defect_category_name: string;
  score: number | null; deterministic_score: number | null; ai_score: number | null; passed: boolean; pass_threshold: number;
  criteria: Record<string, Criterion>; notes: string[]; rubric_version: number; evaluator_version: string;
  ai_status: AiStatus; created_at: string; updated_at: string;
}
export interface ExplanationInput {
  why_failed: string; why_works: string; invariant_preserved: string; side_effects: string; additional_tests: string;
}
export interface ExplanationRecord extends ExplanationInput {
  id: string; problem_id: number; attempt_id: string; submission_id: string | null;
  score: number | null; deterministic_score: number | null; ai_score: number | null;
  criteria: Record<string, Criterion>; notes: string[]; rubric_version: number; evaluator_version: string;
  ai_status: AiStatus; created_at: string;
}
export interface AttemptScores {
  attempt_id: string; context: AttemptContext; status: 'in_progress' | 'solved' | 'completed' | 'expired';
  diagnosis: number | null; correctness: number | null; quality: number | null; explanation: number | null;
  verification: number | null; time: number | null; total: number | null;
  activity: Record<string, unknown>; versions: Record<string, unknown>; solved_at: string | null; started_at: string;
}
export interface DiagnosisStatusResponse {
  required: boolean; mode: 'off' | 'optional' | 'required'; enabled: boolean; submitted: boolean;
  attempt_id: string | null; context: AttemptContext; latest: DiagnosisRecord | null; history: DiagnosisRecord[];
  explanation: ExplanationRecord | null; solved: boolean; scores: AttemptScores | null;
  categories: BugCategory[]; pass_threshold: number;
}

export type Confidence = 'insufficient' | 'low' | 'moderate' | 'high';
export interface MasteryRow {
  id: string; name: string; attempted: number; solved: number; diagnosis_score: number | null;
  mastery: number | null; confidence: Confidence;
}
export interface Insights {
  reasoning: {
    score: number | null; raw_score: number | null; sample_size: number; confidence: Confidence;
    provisional: boolean; message: string;
    dimensions: { id: string; name: string; score: number | null; weight: number }[];
  };
  patch_correctness: number | null; engineering_quality: number | null; explanation_quality: number | null;
  diagnoses: number; solved: number; attempted: number;
  categories: MasteryRow[]; skills: MasteryRow[];
  incidents: { session_id: string; incident_slug: string; title: string; severity: string; status: string;
    score: number | null; started_at: string; resolved_at: string | null }[];
  assessments: { session_id: string; assessment_slug: string; title: string; status: string; finalized: boolean;
    score: number | null; score_hidden: boolean; started_at: string; completed_at: string | null }[];
  trend: { week: string; diagnosis_score: number | null; diagnoses: number; submissions: number; pass_rate: number | null }[];
  recommendations: { slug: string; title: string; difficulty: string; category: string; reason: string }[];
  recommended_concepts: { id: string; name: string }[];
}

export type RubricGroups = string[][];
export interface Rubric {
  version?: number; source?: 'derived' | 'authored' | 'admin'; defect_categories: string[];
  related_categories?: string[]; root_cause: RubricGroups; component: string[];
  invariant?: RubricGroups; correction?: RubricGroups; reproduction?: RubricGroups;
  weights?: Record<string, number>; explanation?: Record<string, RubricGroups>;
}
export interface RubricSummary {
  id: number; slug: string; title: string; category: string; visibility: string;
  diagnosis_mode: 'off' | 'optional' | 'required'; rubric_version: number; rubric_source: 'derived' | 'authored' | 'admin';
}
export interface RubricDetail {
  slug: string; title: string; rubric_version: number; diagnosis_mode: 'off' | 'optional' | 'required';
  source: 'derived' | 'authored' | 'admin'; effective: Rubric; derived: Rubric; stored: Rubric | null;
  categories: BugCategory[];
}

export interface DiagnosisHistoryItem extends DiagnosisRecord {
  problem_slug: string; problem_title: string;
  submissions: { id: string; kind: 'run' | 'submit'; status: string; language: Language; created_at: string }[];
}
