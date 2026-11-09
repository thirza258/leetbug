import { CheckCircle2, CircleDot, LoaderCircle, Sparkles, XCircle } from 'lucide-react';
import { criterionNames, formatScore } from './api';
import type { AiStatus, AttemptScores, Criterion, CriterionLevel } from './types';

const levelLabels: Record<CriterionLevel, string> = { strong: 'Strong', partial: 'Partial', missing: 'Missing' };

export function LevelPill({ level }: { level: CriterionLevel }) {
  const Icon = level === 'strong' ? CheckCircle2 : level === 'partial' ? CircleDot : XCircle;
  return <span className={`dx-pill ${level}`}><Icon size={12} aria-hidden />{levelLabels[level]}</span>;
}

export function AiNote({ status }: { status: AiStatus }) {
  if (status === 'queued' || status === 'running') {
    return <span className="dx-ai" role="status"><LoaderCircle size={12} className="spin" aria-hidden />Semantic review in progress</span>;
  }
  if (status === 'completed') return <span className="dx-ai"><Sparkles size={12} aria-hidden />Includes an AI semantic review</span>;
  if (status === 'failed') return <span className="dx-ai">AI review unavailable; the rubric score stands</span>;
  return null;
}

interface Scored { score: number | null; criteria: Record<string, Criterion>; notes: string[]; ai_status: AiStatus; passed?: boolean }

export function ResultCard({ record, title }: { record: Scored; title: string }) {
  return <section className="dx-result" aria-live="polite" aria-label={title}>
    <div className="dx-result-head">
      <div className="dx-score"><strong>{formatScore(record.score)}</strong><span>/ 100</span></div>
      <div>
        <strong style={{ display: 'block', fontSize: 13, fontWeight: 500 }}>{title}</strong>
        {record.passed !== undefined && <span className={`dx-pill ${record.passed ? 'pass' : 'fail'}`} style={{ marginTop: 6 }}>
          {record.passed ? <CheckCircle2 size={12} aria-hidden /> : <XCircle size={12} aria-hidden />}
          {record.passed ? 'Meets the diagnosis bar' : 'Below the diagnosis bar'}</span>}
      </div>
      <AiNote status={record.ai_status} />
    </div>
    <ul className="dx-criteria">{Object.entries(record.criteria).map(([name, item]) => <li key={name}>
      <strong>{criterionNames[name] ?? name}<small>{item.weight}%</small></strong><LevelPill level={item.level} />
      <p>{item.feedback}</p>
    </li>)}</ul>
    {record.notes.length > 0 && <ul className="dx-notes">{record.notes.map(note => <li key={note}>{note}</li>)}</ul>}
  </section>;
}

export function AttemptScoreGrid({ scores }: { scores: AttemptScores }) {
  const tiles = [
    { label: 'Diagnosis', value: scores.diagnosis },
    { label: 'Patch correctness', value: scores.correctness },
    { label: 'Engineering quality', value: scores.quality },
    { label: 'Explanation', value: scores.explanation },
  ];
  return <section aria-label="Scores for this challenge">
    <div className="problem-context-label"><span />SCORED SEPARATELY</div>
    <div className="dx-scores">{tiles.map(tile => <div key={tile.label}><span>{tile.label}</span><strong>{formatScore(tile.value)}</strong></div>)}</div>
  </section>;
}
