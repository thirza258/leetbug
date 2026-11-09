import { AlertTriangle, History, Info, LoaderCircle, Send } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ErrorState, Loading } from '../../components/ui';
import type { Language, ProblemDetail } from '../../types';
import { formatScore, submitDiagnosis, useDiagnosisStatusQuery } from './api';
import type { SessionOptions } from './api';
import { AttemptScoreGrid, LevelPill, ResultCard } from './parts';
import type { BugCategory, DiagnosisInput, DiagnosisRecord } from './types';
import './diagnosis.css';

// Props are a fixed contract used by Workspace, AssessmentRunner and IncidentWorkspace.
export interface DiagnosisPanelProps {
  problem: ProblemDetail; language: Language;
  assessmentSessionId?: string; incidentSessionId?: string;
  onSubmitted?: () => void;
}

type TextField = Exclude<keyof DiagnosisInput, 'defect_category'>;
const FIELDS: { key: TextField; label: string; hint: string; max: number }[] = [
  { key: 'root_cause', label: 'Root cause', hint: 'Why does the program fail? Name the operation or condition that goes wrong.', max: 4000 },
  { key: 'affected_component', label: 'Affected component', hint: 'The function, variable, or module where the defect lives.', max: 1000 },
  { key: 'violated_invariant', label: 'Violated invariant', hint: 'What should always (or never) be true, and is not?', max: 2000 },
  { key: 'proposed_correction', label: 'Proposed correction', hint: 'The change you intend to make, described at a high level.', max: 4000 },
  { key: 'reproduction_strategy', label: 'Reproduction strategy', hint: 'How would you trigger the failure on purpose, and what would you observe?', max: 4000 },
];

export default function DiagnosisPanel({ problem, language, assessmentSessionId, incidentSessionId, onSubmitted }: DiagnosisPanelProps) {
  const options: SessionOptions = { assessmentSessionId, incidentSessionId };
  const status = useDiagnosisStatusQuery(problem.slug, { enabled: true, ...options });
  if (status.isPending) return <Loading label="Loading your diagnosis…" />;
  if (status.isError) return <ErrorState error={status.error} retry={() => void status.refetch()} />;
  const data = status.data;
  return <div className="dx-panel">
    <div className="dx-intro"><span className="eyebrow">DIAGNOSE BEFORE YOU FIX</span><h2>What is really going wrong?</h2>
      <p>Describe the defect in your own words before you change the code. Your diagnosis is scored separately from your patch, so a passing fix does not replace a clear explanation of the cause.</p></div>
    {data.required && !data.submitted && <div className="dx-notice"><AlertTriangle size={15} aria-hidden /><span>This challenge requires a diagnosis before you can submit a fix. Running the public tests is still available.</span></div>}
    {!data.enabled ? <div className="dx-notice info"><Info size={15} aria-hidden /><span>Diagnosis is turned off for this case study.</span></div> : <>
      {data.latest && <ResultCard record={data.latest} title={`Your diagnosis · revision ${data.latest.revision}`} />}
      {data.scores && <AttemptScoreGrid scores={data.scores} />}
      <DiagnosisForm key={data.latest?.id ?? 'new'} slug={problem.slug} language={language} categories={data.categories}
        initial={data.latest} options={options} onSubmitted={onSubmitted} />
      {data.history.length > 1 && <details className="dx-history"><summary><History size={13} aria-hidden /> Revision history ({data.history.length})</summary>
        <ol>{data.history.map(row => <li key={row.id}><strong>Revision {row.revision}</strong><span>{row.defect_category_name}</span>
          <LevelPill level={row.passed ? 'strong' : (row.score ?? 0) >= 35 ? 'partial' : 'missing'} />
          <span>{formatScore(row.score)} / 100</span><span>{new Date(row.created_at).toLocaleString()}</span></li>)}</ol>
      </details>}
    </>}
  </div>;
}

function DiagnosisForm({ slug, language, categories, initial, options, onSubmitted }: {
  slug: string; language: Language; categories: BugCategory[]; initial: DiagnosisRecord | null;
  options: SessionOptions; onSubmitted?: () => void;
}) {
  const client = useQueryClient();
  const [values, setValues] = useState<DiagnosisInput>(() => ({
    defect_category: initial?.defect_category ?? '', root_cause: initial?.root_cause ?? '',
    affected_component: initial?.affected_component ?? '', violated_invariant: initial?.violated_invariant ?? '',
    proposed_correction: initial?.proposed_correction ?? '', reproduction_strategy: initial?.reproduction_strategy ?? '',
  }));
  const submit = useMutation({
    mutationFn: () => submitDiagnosis(slug, { ...values, language }, options),
    onSuccess: async row => {
      toast.success(row.passed ? 'Diagnosis recorded. It meets the bar.' : 'Diagnosis recorded. Review the feedback to sharpen it.');
      await client.invalidateQueries({ queryKey: ['diagnosis', slug] });
      onSubmitted?.();
    },
    onError: error => toast.error(error.message),
  });
  const complete = Object.values(values).every(value => value.trim().length > 0);
  const selected = categories.find(category => category.id === values.defect_category);
  return <form className="dx-form" onSubmit={event => { event.preventDefault(); if (complete) submit.mutate(); }}>
    <div className="problem-context-label"><span />{initial ? 'REVISE YOUR DIAGNOSIS' : 'YOUR DIAGNOSIS'}</div>
    <label className="dx-field">Defect category
      <select value={values.defect_category} required onChange={event => setValues({ ...values, defect_category: event.target.value })}>
        <option value="">Choose the category that fits best</option>
        {categories.map(category => <option key={category.id} value={category.id}>{category.name}</option>)}
      </select>
      <small>{selected?.description ?? 'Classify the defect by how it fails, not by where it appears.'}</small>
    </label>
    {FIELDS.map(field => <label className="dx-field" key={field.key}>{field.label}
      <textarea value={values[field.key]} maxLength={field.max} required
        onChange={event => setValues({ ...values, [field.key]: event.target.value })} />
      <small>{field.hint}</small>
    </label>)}
    <div className="dx-form-actions"><span>Feedback is general on purpose: it never reveals the answer.</span>
      <button className="button primary small" type="submit" disabled={!complete || submit.isPending}>
        {submit.isPending ? <LoaderCircle size={14} className="spin" aria-hidden /> : <Send size={13} aria-hidden />}
        {initial ? 'Submit revision' : 'Submit diagnosis'}</button></div>
  </form>;
}
