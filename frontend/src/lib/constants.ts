import { Braces, BriefcaseBusiness, CornerDownRight, Zap } from 'lucide-react';
import type { Category, Language, Status } from '../types';

export const languageNames: Record<Language, string> = { python: 'Python', java: 'Java', javascript: 'JavaScript', cpp: 'C++', go: 'Go' };
export const categories = {
  runtime: { name: 'Runtime errors', short: 'Runtime', description: 'Stop the crash.', icon: Zap, color: 'coral' },
  logic: { name: 'Logic errors', short: 'Logic', description: 'Find the missing piece.', icon: Braces, color: 'purple' },
  business: { name: 'Business flow', short: 'Business flow', description: 'Protect the bigger picture.', icon: BriefcaseBusiness, color: 'blue' },
  edge: { name: 'Edge & corner cases', short: 'Edge cases', description: 'Expect the unexpected.', icon: CornerDownRight, color: 'amber' },
} satisfies Record<Category, { name: string; short: string; description: string; icon: typeof Zap; color: string }>;
export const statusNames: Record<Status, string> = {
  queued: 'Queued', running: 'Evaluating', passed: 'Passed', failed: 'Failed', runtime_error: 'Runtime error',
  time_limit: 'Time limit', memory_limit: 'Memory limit', output_limit: 'Output limit', error: 'Service error',
};
export const pending = (status?: string) => status === 'queued' || status === 'running';
export const ms = (value?: number | null) => value == null ? '—' : value >= 1000 ? `${(value / 1000).toFixed(2)} s` : `${Math.round(value)} ms`;
export const dateLabel = (value: string) => new Date(value.endsWith('Z') || value.includes('+') ? value : `${value}Z`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });

