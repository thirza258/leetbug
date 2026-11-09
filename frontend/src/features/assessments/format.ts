import type { AssessmentType, SessionStatus } from './types';

export const typeNames: Record<AssessmentType, string> = {
  individual: 'Skill assessment', interview: 'Technical interview', specialized: 'Specialized', practice: 'Practice',
};
export const aiNames = { disabled: 'No AI', guided: 'Guided AI', enabled: 'AI allowed' } as const;
export const hintNames = { disabled: 'No hints', restricted: 'First hint only', enabled: 'Hints allowed' } as const;
export const sessionNames: Record<SessionStatus, string> = { active: 'In progress', completed: 'Completed', expired: 'Time expired', cancelled: 'Cancelled' };
export const dimensionNames = {
  diagnosis: 'Diagnosis', correctness: 'Correctness', verification: 'Verification', quality: 'Code quality',
  explanation: 'Explanation', time: 'Time efficiency',
} as const;

export function minutes(seconds: number) { return `${Math.round(seconds / 60)} min`; }
export function clock(seconds: number) {
  const value = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(value / 3600);
  const rest = `${String(Math.floor(value % 3600 / 60)).padStart(2, '0')}:${String(value % 60).padStart(2, '0')}`;
  return hours ? `${hours}:${rest}` : rest;
}
export function score(value: number | null | undefined) { return value == null ? '—' : `${Math.round(value)}%`; }
export function when(value: string | null | undefined) { return value ? new Date(value).toLocaleString() : '—'; }
