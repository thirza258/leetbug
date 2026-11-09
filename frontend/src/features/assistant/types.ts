export type AssistantIntent =
  | 'explain_problem' | 'explain_runtime_error' | 'identify_failing_test' | 'review_patch' | 'why_fix_failed'
  | 'reproduction_strategy' | 'explain_concept' | 'find_documentation' | 'progressive_hint' | 'review_diagnosis';
export interface AssistantSection { key: string; title: string; body: string }
export interface AssistantSource { title: string; url: string; excerpt: string; language: string | null; score: number }
export interface AssistantValidation {
  redacted_hidden?: number; solution_like?: number; reference_overlap?: number; long_code_blocks?: number;
  invalid_citations?: number; unverified_urls?: number; limitation_added?: boolean; blocked?: boolean;
  low_grounding?: boolean; grounding_score?: number; deterministic_backfill?: string[];
}
export interface AssistantInteraction {
  id: string; problem_id: number; attempt_id: string | null; assessment_session_id: string | null;
  intent: AssistantIntent; intent_label: string; question: string;
  status: 'queued' | 'running' | 'completed' | 'error'; context_version: string;
  context: Record<string, unknown>;
  response: { intent: AssistantIntent; label: string; sections: AssistantSection[]; generation: string } | null;
  response_text: string | null; sources: AssistantSource[];
  retrieval: { method: string | null; selected: string[] | null; topics: string[] | null; latency_ms: number | null };
  metadata: {
    generation: 'deterministic' | 'model' | 'model-fallback' | null; model: string | null;
    grounding_score: number | null; limitations: string[] | null; validation: AssistantValidation | null;
    intent_confidence: number | null;
  };
  token_usage: number | null; latency_ms: number | null; retrieval_ms: number | null; generation_ms: number | null;
  error: string | null; created_at: string; completed_at: string | null;
}
export interface AssistantRequest {
  language: string; code?: string; submission_id?: string;
  assessment_session_id?: string; incident_session_id?: string; question?: string;
}
