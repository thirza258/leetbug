import type { ArtifactType, Severity, TimelineKind } from './types';

export const levelNames: Record<number, string> = {
  1: 'Component debugging', 2: 'Application debugging', 3: 'Distributed debugging', 4: 'Production investigation',
};
export const severityTone: Record<Severity, string> = { 'SEV-1': 'coral', 'SEV-2': 'amber', 'SEV-3': 'blue', 'SEV-4': 'teal' };
export const artifactNames: Record<ArtifactType, string> = {
  logs: 'Logs', metrics: 'Metrics', traces: 'Traces', database: 'Database snapshot', config: 'Configuration',
  diff: 'Deployment diff', architecture: 'Architecture', source: 'Source', api_contract: 'API contract', runbook: 'Runbook',
};
export const observabilityTypes: ArtifactType[] = ['logs', 'metrics', 'traces'];
export const contextTypes: ArtifactType[] = ['source', 'config', 'diff', 'database', 'api_contract', 'architecture', 'runbook'];
export const timelineNames: Record<TimelineKind, string> = { deploy: 'Deploy', alert: 'Alert', symptom: 'Symptom', action: 'Action', note: 'Note' };
export const dimensionNames: Record<string, string> = {
  root_cause: 'Root-cause identification', investigation: 'Reproduction and investigation', fix: 'Fix correctness',
  regression: 'Regression prevention', remediation: 'Operational remediation', communication: 'Explanation and communication',
};
export const dimensionOrder = ['root_cause', 'investigation', 'fix', 'regression', 'remediation', 'communication'];

/** Parse a timestamp or a numeric offset to a number for plotting; NaN when neither. */
export function toTime(value: string | number): number {
  return typeof value === 'number' ? value : Date.parse(value);
}
export function clock(value: string | number): string {
  if (typeof value === 'number') return String(value);
  const time = Date.parse(value);
  if (Number.isNaN(time)) return value;
  return new Date(time).toISOString().slice(11, 19);
}
export function score(value: number | null | undefined): string {
  return value == null ? '—' : `${Math.round(value)}`;
}
export function compactNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${(value / 1000).toFixed(1)}k`;
  if (abs !== 0 && abs < 1) return value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}
