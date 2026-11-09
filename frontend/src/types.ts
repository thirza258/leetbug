export type Language = 'python' | 'java' | 'javascript' | 'cpp' | 'go';
export type Category = 'runtime' | 'logic' | 'business' | 'edge' | 'system_design' | 'data_science' | 'data_analytics';
export type Mode = 'manual' | 'ai';
export type Status = 'queued' | 'running' | 'passed' | 'failed' | 'runtime_error' | 'time_limit' | 'memory_limit' | 'output_limit' | 'error';
export interface User { id: string; email: string; username: string; bio: string; created_at: string; is_admin: boolean; }
export interface Session { user: User | null; csrf_token: string | null }
export interface Meta { ai_enabled: boolean; ai_provider: string; ai_model: string | null; hint_failure_threshold: number; demo_available: boolean; problem_count: number; features?: Record<string, boolean> }
export interface Page<T> { items: T[]; total: number; page: number; limit: number }
export interface Problem {
  id: number; slug: string; title: string; summary: string; category: Category;
  difficulty: 'easy' | 'medium' | 'hard'; tags: string[]; languages: Language[];
  estimated_minutes: number; status: 'solved' | 'attempted' | 'todo'; bookmarked: boolean;
  acceptance_rate: number | null;
}
export interface TestCase { name: string; input: unknown; expected: unknown; assertions: { path: string; equals: unknown }[] }
export interface TaxonomyLabel { id: string; name: string }
export interface Assistance { ai: 'disabled' | 'guided' | 'enabled'; hints: 'disabled' | 'restricted' | 'enabled'; source: 'practice' | 'assessment'; assessment_session_id: string | null }
export interface ProblemDetail extends Problem {
  description: string; requirements: string[]; starters: Partial<Record<Language, string>>;
  public_tests: TestCase[]; hidden_test_count: number; failed_attempts: number; hints_unlocked: boolean;
  visibility: 'public' | 'incident' | 'assessment' | 'draft'; version: number;
  diagnosis_mode: 'off' | 'optional' | 'required'; diagnosis_required: boolean;
  taxonomy: { bug_categories: TaxonomyLabel[]; skills: TaxonomyLabel[] }; assistance: Assistance;
}
export interface DiffStats { added: number; removed: number; changed_original_lines: number[]; original_lines: number; current_lines: number; unchanged: boolean }
export interface PatchQuality { score: number; version: string; dimensions: Record<string, { score: number | null; detail: string }> }
export interface TestResult {
  name: string; hidden: boolean; status: Status; input?: unknown; expected?: unknown; actual?: unknown;
  message?: string; runtime_ms?: number; assertions?: { path: string; passed: boolean; expected: unknown }[];
}
export interface Submission {
  id: string; problem_id: number; problem_slug: string; problem_title: string;
  language: Language; mode: Mode; kind: 'run' | 'submit'; code: string; prompt: string;
  generated_code: string | null; status: Status; results: TestResult[]; error: string | null;
  runtime_ms: number | null; memory_kb: number | null; turnaround_ms: number | null;
  llm_tokens: number | null; prompt_words: number; shared: boolean; created_at: string;
  attempt_id?: string | null; assessment_session_id?: string | null; diagnosis_id?: string | null;
  diff_stats?: DiffStats | null; quality?: PatchQuality | null;
}
export interface Hint {
  id: string; level: number; status: 'queued' | 'running' | 'completed' | 'error'; text: string | null;
  sources: { title: string; url: string; excerpt: string }[]; retrieval: string | null; error: string | null;
}
export interface Solutions {
  explanation: string; solutions: Partial<Record<Language, string>>;
  community: { id: string; username: string; language: Language; mode: Mode; code: string; prompt: string; prompt_words: number; runtime_ms: number }[];
}
export interface Metrics {
  attempts: number; passed_attempts: number; completion_rate: number; manual_attempts: number;
  ai_attempts: number; manual_p95_ms: number | null; ai_p95_ms: number | null;
}
export interface PersonalStats extends Metrics {
  solved: number; total_problems: number; streak: number;
  categories: { category: Category; solved: number; total: number }[];
  activity: { date: string; count: number }[];
  achievements: { name: string; description: string; unlocked: boolean }[];
}
export interface PlatformStats extends Metrics {
  registered_users: number; monthly_active_users: number; retention_7d: number | null;
  retention_cohort_size: number; manual_target_ms: number; ai_target_ms: number;
}
export interface Rank { user_id: string; username: string; rank: number; solved: number; prompt_words: number | null; runtime_ms: number }
export interface Reply { id: string; body: string; author: string; author_id: string; created_at: string }
export interface Discussion {
  id: string; title: string; body: string; author: string; author_id: string; created_at: string;
  problem_id: number | null; problem_title: string | null; problem_slug: string | null;
  votes: number; voted: boolean; reply_count: number; replies: Reply[];
}

export interface ProblemSubmission {
  id: string;
  author_id: string;
  author_username?: string;
  title: string;
  slug: string;
  summary: string;
  description: string;
  category: Category;
  difficulty: 'easy' | 'medium' | 'hard';
  tags: string[];
  language: Language;
  buggy_code: string;
  fixed_code: string;
  test_cases: { input: unknown; expected: unknown }[];
  hint: string;
  status: 'pending' | 'approved' | 'rejected';
  admin_notes: string;
  reviewed_at: string | null;
  reviewed_by: string | null;
  created_at: string;
}
