import type { AdminAssessment, AssistancePolicy } from '../assessments/types';

export type OrgRole = 'owner' | 'admin' | 'reviewer';
export interface Organization {
  id: string; slug: string; name: string; role: OrgRole; created_at: string;
  counts: { members: number; assessments: number; finalized_sessions: number };
  permissions: { manage: boolean; review: boolean; owner: boolean };
}
export interface Member { user_id: string; username: string; email: string; role: OrgRole; joined_at: string }
export type OrgAssessment = AdminAssessment;
export interface CandidateRow {
  session_id: string; assessment_id: string; assessment_slug: string; assessment_title: string;
  assessment_version: number | null; candidate: { id: string; username: string; email: string };
  status: string; started_at: string | null; completed_at: string | null; finalized_at: string | null;
  total_score: number | null; report_version: number; released: boolean; challenges_completed: number | null;
  challenges_total: number | null; time_spent_seconds: number | null; ai_used: number; hints_used: number;
  assistance_policy: AssistancePolicy; corrected: boolean;
}
export interface ComparisonColumn extends CandidateRow {
  competencies: Record<string, number | null>;
  behavior: { submissions?: number; diagnosis_accuracy?: number | null; avg_time_per_challenge_seconds?: number | null; explanation_quality?: number | null; failed_test_patterns?: Record<string, number> };
  profile: { score: number | null; coverage: number } | null;
  challenges: Record<string, { status: string; total: number | null; components: Record<string, number | null> }>;
  disclaimers: string[];
}
export interface Comparison {
  sessions: ComparisonColumn[]; challenges: { key: string; title: string | null }[];
  competency_areas: { id: string; name: string }[]; same_assessment: boolean; notes: string[];
}
export interface HistogramBucket { from: number; to: number; count: number }
export interface ChallengeStatistic {
  slug: string; title: string | null; difficulty_label: string | null; sessions: number;
  mean_correctness: number | null; mean_score: number | null; solve_rate: number | null;
  discrimination_index: number | null; discrimination_status: 'ok' | 'insufficient_data';
}
export interface Analytics {
  organization: { id: string; slug: string; name: string }; assessment_id: string | null;
  assessments: { id: string; slug: string; title: string; status: string; visibility: string; sessions: number;
    status_counts: Record<string, number>; finalized: number; completion_rate: number | null;
    mean_score: number | null; median_score: number | null }[];
  totals: { sessions: number; finalized: number; active: number; completion_rate: number | null; mean_score: number | null; median_score: number | null };
  score_distribution: HistogramBucket[];
  competencies: { id: string; name: string; mean: number | null; sessions: number }[];
  challenges: ChallengeStatistic[];
  assistance: { ai_usage_share: number | null; hint_usage_share: number | null; ai_policies: Record<string, number>; hint_policies: Record<string, number> };
  thresholds: { discrimination_min_sessions: number; group_share: number }; notes: string[];
}
export interface OrgInvitation {
  id: string; assessment_id: string; assessment_slug: string; assessment_title: string; email: string;
  status: 'pending' | 'accepted' | 'revoked' | 'expired'; created_at: string | null; expires_at: string | null; accepted_at: string | null;
}
export interface CompetencyProfile {
  id: string; organization_id: string | null; slug: string; name: string; description: string;
  weights: Record<string, number>; scope: 'organization' | 'global'; assessments_using: number; created_at: string | null;
}
export interface Taxonomy {
  bug_categories: { id: string; name: string }[]; skills: { id: string; name: string }[];
  competency_areas: { id: string; name: string }[];
}
