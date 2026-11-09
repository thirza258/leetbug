import type { Language, ProblemDetail, Status } from '../../types';

export type AssessmentType = 'individual' | 'interview' | 'specialized' | 'practice';
export type AiPolicy = 'disabled' | 'guided' | 'enabled';
export type HintPolicy = 'disabled' | 'restricted' | 'enabled';
export type SessionStatus = 'active' | 'completed' | 'expired' | 'cancelled';
export type Dimension = 'diagnosis' | 'correctness' | 'verification' | 'quality' | 'explanation' | 'time';
export interface AssistancePolicy { ai: AiPolicy; hints: HintPolicy }

export interface AssessmentConfiguration {
  problems: string[]; languages: Language[]; diagnosis_required: boolean; explanation_required: boolean;
  max_attempts: number | null; max_sessions: number | null; randomize_order: boolean;
  feedback: 'immediate' | 'delayed'; candidate_report: 'full' | 'summary'; require_quality_approved: boolean;
}
export interface SessionBrief {
  id: string; status: SessionStatus; started_at: string; expires_at: string; completed_at: string | null;
  finalized_at: string | null; total_score: number | null; released: boolean;
}
export interface AssessmentCard {
  id: string; slug: string; title: string; description: string; assessment_type: AssessmentType;
  duration_seconds: number; challenge_count: number; difficulty_mix: { easy: number; medium: number; hard: number };
  languages: Language[]; assistance_policy: AssistancePolicy; diagnosis_required: boolean; explanation_required: boolean;
  max_attempts: number | null; max_sessions: number | null; feedback: 'immediate' | 'delayed';
  candidate_report: 'full' | 'summary'; visibility: 'public' | 'private' | 'invitation';
  status: 'draft' | 'published' | 'archived'; organization_id: string | null; version: number;
  available_from: string | null; available_until: string | null; my_session: SessionBrief | null;
}
export interface AssessmentDetail extends AssessmentCard {
  rules: string[]; recovery_rule: string; sessions_used: number; active_session_id: string | null;
  can_start: boolean; start_blocker: string | null;
}
export interface AdminAssessment extends AssessmentCard {
  configuration: AssessmentConfiguration; scoring_rubric: { weights: Partial<Record<Dimension, number>> };
  competency_profile_id: string | null; created_by: string | null; created_at: string; updated_at: string;
  session_counts: Record<string, number>; invitation_counts: Record<string, number>; validation_errors: string[];
}
export interface ChallengeSubmission { id: string; kind: 'run' | 'submit'; status: Status; language: Language; mode: 'manual' | 'ai'; created_at: string }
export interface SessionChallenge {
  position: number; problem_id: number; slug: string; title: string; difficulty: string; category: string;
  status: 'not_started' | 'in_progress' | 'solved'; submissions_used: number; max_attempts: number | null;
  diagnosis_submitted: boolean; explanation_submitted: boolean; submissions: ChallengeSubmission[];
  problem?: ProblemDetail;
}
export interface AssessmentSessionView {
  id: string; status: SessionStatus; viewer: 'candidate' | 'reviewer'; started_at: string; expires_at: string;
  completed_at: string | null; finalized_at: string | null; server_time: string; remaining_seconds: number;
  candidate: { id: string; username: string | null };
  assessment: {
    id: string; slug: string; title: string; assessment_type: AssessmentType; version: number; duration_seconds: number;
    assistance_policy: AssistancePolicy;
    configuration: Pick<AssessmentConfiguration, 'languages' | 'diagnosis_required' | 'explanation_required' | 'max_attempts' | 'feedback' | 'candidate_report'>;
  };
  challenges: SessionChallenge[]; pending_evaluations: number; report_ready: boolean; report_released: boolean;
  recovery_rule: string;
}
export interface MySession extends SessionBrief {
  assessment: { id: string; slug: string; title: string; assessment_type: AssessmentType }; challenge_count: number;
}
export interface ReportChallenge {
  position: number; problem_id?: number; slug?: string; title: string; status: 'not_started' | 'attempted' | 'solved';
  total: number; category?: string; difficulty?: string; bug_categories?: string[]; skills?: string[];
  components?: Record<Dimension, number | null>; weights?: Partial<Record<Dimension, number>>;
  submissions?: number; runs?: number; time_spent_seconds?: number; hints?: number; ai_interactions?: number;
  ai_submissions?: number; diagnosis_submitted?: boolean; explanation_submitted?: boolean;
  failed_statuses?: string[]; attempts_to_cause?: number | null; corrected?: boolean;
}
export interface Competency { id: string; name: string; dimension: string; score: number | null; evidence_count: number; assessed: boolean }
export interface DevelopmentArea { id: string; area: string; score: number; evidence: string; recommendation: string; practice: { slug: string; title: string; difficulty: string }[] }
export interface Behavior {
  submissions: number; runs: number; avg_submissions_per_challenge: number; diagnosis_accuracy: number | null;
  diagnosis_coverage: number; hints_used: number; ai_interactions: number; ai_submissions: number;
  avg_time_per_challenge_seconds: number | null; failed_test_patterns: Record<string, number>;
  explanation_quality: number | null; explanations_submitted: number; challenges_started: number;
}
export interface Correction { report_version: number; actor_id: string; reason: string; before_total: number | null; after_total: number; at: string }
export interface ReportSummary {
  candidate: { id: string; username: string | null };
  assessment: { id: string; slug: string; title: string; type: AssessmentType; version: number };
  status: SessionStatus; total_score: number; time_spent_seconds: number; duration_seconds: number;
  challenges_completed: number; challenges_total: number; started_at: string; ended_at: string; evaluated_at: string;
}
export interface AssessmentReport {
  level: 'full' | 'summary' | 'pending_review' | 'finalizing'; released?: boolean; viewer?: 'candidate' | 'reviewer';
  report_version?: number; summary?: Partial<ReportSummary>; challenges?: ReportChallenge[];
  competencies?: Competency[]; profile?: { score: number | null; coverage: number } | null; behavior?: Behavior;
  development_areas?: DevelopmentArea[];
  assistance?: { policy: AssistancePolicy; hints_used: number; ai_interactions: number; ai_submissions: number; assisted: boolean; unaided_policy: boolean };
  disclaimers?: string[]; recovery_rule?: string; corrections?: Correction[]; weights?: Partial<Record<Dimension, number>>;
  pending_evaluations?: number; status?: SessionStatus;
}
export interface AdminSession extends SessionBrief {
  report_version: number; assessment_version: number; candidate: { id: string; username: string; email: string };
}
export interface Invitation { id: string; email: string; status: string; created_at: string; expires_at: string | null; accepted_at: string | null }
export interface CreatedInvitation { id: string; email: string; token: string; path: string; expires_at: string }
