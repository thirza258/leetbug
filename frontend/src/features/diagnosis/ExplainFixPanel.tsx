import { LoaderCircle, MessageSquareText, Send } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import type { ProblemDetail, Submission } from '../../types';
import { submitExplanation, useDiagnosisStatusQuery } from './api';
import type { SessionOptions } from './api';
import { ResultCard } from './parts';
import type { ExplanationInput, ExplanationRecord } from './types';
import './diagnosis.css';

// Shown after an accepted full submission (PRD 5.2 Stage E, 10.5).
export interface ExplainFixPanelProps {
  problem: ProblemDetail; submission: Submission;
  assessmentSessionId?: string; incidentSessionId?: string; required?: boolean;
}

const FIELDS: { key: keyof ExplanationInput; label: string; hint: string; max: number; optional?: boolean }[] = [
  { key: 'why_failed', label: 'Why the original failed', hint: 'The mechanism that broke the expected behavior.', max: 4000 },
  { key: 'why_works', label: 'Why your fix works', hint: 'Why the change removes the cause, beyond the tests passing.', max: 4000 },
  { key: 'invariant_preserved', label: 'Invariant now preserved', hint: 'The rule that is now always (or never) true.', max: 2000 },
  { key: 'side_effects', label: 'Possible side effects', hint: 'Behavior, performance, or compatibility risks, or why there are none.', max: 2000, optional: true },
  { key: 'additional_tests', label: 'Additional tests', hint: 'One regression test per line: the input and the expected result.', max: 4000, optional: true },
];

export default function ExplainFixPanel({ problem, submission, assessmentSessionId, incidentSessionId, required }: ExplainFixPanelProps) {
  const { user } = useAuth();
  const options: SessionOptions = { assessmentSessionId, incidentSessionId };
  const status = useDiagnosisStatusQuery(problem.slug, { enabled: !!user, ...options });
  if (!user) return null;
  const existing = status.data?.explanation ?? null;
  return <details className="dx-explain" open={required && !existing ? true : undefined}>
    <summary><MessageSquareText size={16} aria-hidden />Explain your fix
      <span className={`dx-pill ${required ? 'partial' : 'neutral'}`}>{existing ? 'Submitted' : required ? 'Required' : 'Optional'}</span></summary>
    <div className="dx-explain-body">
      <p className="muted" style={{ fontSize: 12 }}>A short explanation shows that you understand the defect, not only the patch. It is scored separately and never changes your test results.</p>
      {existing && <ResultCard record={existing} title="Your explanation" />}
      <ExplanationForm key={existing?.id ?? 'new'} slug={problem.slug} submissionId={submission.id} initial={existing} options={options} />
    </div>
  </details>;
}

function ExplanationForm({ slug, submissionId, initial, options }: {
  slug: string; submissionId: string; initial: ExplanationRecord | null; options: SessionOptions;
}) {
  const client = useQueryClient();
  const [values, setValues] = useState<ExplanationInput>(() => ({
    why_failed: initial?.why_failed ?? '', why_works: initial?.why_works ?? '',
    invariant_preserved: initial?.invariant_preserved ?? '', side_effects: initial?.side_effects ?? '',
    additional_tests: initial?.additional_tests ?? '',
  }));
  const submit = useMutation({
    mutationFn: () => submitExplanation(slug, { ...values, submission_id: submissionId }, options),
    onSuccess: async () => {
      toast.success('Explanation recorded.');
      await client.invalidateQueries({ queryKey: ['diagnosis', slug] });
    },
    onError: error => toast.error(error.message),
  });
  const complete = FIELDS.every(field => field.optional || values[field.key].trim().length > 0);
  return <form className="dx-form" onSubmit={event => { event.preventDefault(); if (complete) submit.mutate(); }}>
    {FIELDS.map(field => <label className="dx-field" key={field.key}>{field.label}{field.optional ? ' (optional)' : ''}
      <textarea value={values[field.key]} maxLength={field.max} required={!field.optional}
        onChange={event => setValues({ ...values, [field.key]: event.target.value })} />
      <small>{field.hint}</small>
    </label>)}
    <div className="dx-form-actions"><span>You can revise it later; the latest version counts.</span>
      <button className="button primary small" type="submit" disabled={!complete || submit.isPending}>
        {submit.isPending ? <LoaderCircle size={14} className="spin" aria-hidden /> : <Send size={13} aria-hidden />}
        {initial ? 'Submit revision' : 'Submit explanation'}</button></div>
  </form>;
}
