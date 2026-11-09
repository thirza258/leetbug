import { CheckCircle2, CircleSlash, ClipboardList, LoaderCircle, Plus, RotateCcw, Send, Stethoscope, Trash2, XCircle } from 'lucide-react';
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';
import { dateLabel, statusNames } from '../../lib/constants';
import DiagnosisPanel from '../diagnosis/DiagnosisPanel';
import { resolve, retryResolution } from './api';
import { dimensionNames, dimensionOrder, score } from './format';
import type { Resolution, SessionPayload } from './types';

interface DraftTest { name: string; input: string; expected: string }
const MAX_TESTS = 10;
const MAX_BYTES = 5 * 1024;
const MIN_TEXT = 20;

function parse(text: string): { ok: true; value: unknown } | { ok: false } {
  try { return { ok: true, value: JSON.parse(text) }; } catch { return { ok: false }; }
}
function testProblem(test: DraftTest): string | null {
  const input = parse(test.input); const expected = parse(test.expected);
  if (!test.input.trim() || !input.ok) return 'Input must be valid JSON.';
  if (!test.expected.trim() || !expected.ok) return 'Expected output must be valid JSON.';
  if (new TextEncoder().encode(JSON.stringify({ input: input.value, expected: expected.value })).length > MAX_BYTES) return 'Keep each test under 5 KB.';
  return null;
}

export function ResolutionScore({ resolution, weights }: { resolution: Resolution; weights: Record<string, number> }) {
  const scores = resolution.scores;
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0) || 1;
  return <div className="resolution-score">
    <div className="resolution-total"><strong>{score(resolution.score)}</strong><span>/ 100</span>
      <div className="resolution-outcomes">
        <span className={scores.outcome?.fixed_immediate_defect ? 'ok' : 'no'}>{scores.outcome?.fixed_immediate_defect ? <CheckCircle2 size={13} /> : <XCircle size={13} />}Immediate defect fixed</span>
        <span className={scores.outcome?.prevented_recurrence ? 'ok' : 'no'}>{scores.outcome?.prevented_recurrence ? <CheckCircle2 size={13} /> : <XCircle size={13} />}Recurrence prevented</span>
      </div>
    </div>
    <div className="resolution-dimensions">{dimensionOrder.map(key => {
      const value = scores.components?.[key] ?? 0;
      return <div key={key} className="resolution-dimension">
        <div><span>{dimensionNames[key]}</span><span className="muted">{Math.round((weights[key] ?? 0) / total * 100)}%</span><strong>{score(value)}</strong></div>
        <div className="progress-track"><span className={value >= 70 ? 'green' : value >= 40 ? 'amber' : 'coral'} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>
      </div>;
    })}</div>
    {resolution.regression_results.length > 0 && <div className="incident-table-wrap"><table className="regression-table">
      <thead><tr><th>REGRESSION TEST</th><th>VALID</th><th>CATCHES THE BUG</th><th>YOUR FIX</th><th>CREDIT</th></tr></thead>
      <tbody>{resolution.regression_results.map(row => <tr key={row.name}>
        <td><strong>{row.name}</strong><small>{row.reason}</small></td>
        <td>{row.valid ? <CheckCircle2 size={15} className="green" aria-label="Valid" /> : <XCircle size={15} className="coral" aria-label="Invalid" />}</td>
        <td>{row.detects_bug ? <CheckCircle2 size={15} className="green" aria-label="Detects the bug" /> : <CircleSlash size={15} className="muted" aria-label="Does not detect the bug" />}</td>
        <td>{row.your_fix_status ? statusNames[row.your_fix_status] ?? row.your_fix_status : '—'}</td>
        <td className="mono">{row.credit}</td>
      </tr>)}</tbody>
    </table></div>}
  </div>;
}

export default function ResolutionPanel({ payload, onChanged }: { payload: SessionPayload; onChanged: () => void }) {
  const { problem, session, resolutions } = payload;
  const latest = resolutions[0];
  const closed = session.status !== 'active';
  const [impact, setImpact] = useState('');
  const [remediation, setRemediation] = useState('');
  const [prevention, setPrevention] = useState('');
  const [tests, setTests] = useState<DraftTest[]>([{ name: 'Regression 1', input: '{\n  \n}', expected: '' }]);
  const [submissionId, setSubmissionId] = useState('');
  const fixes = payload.submissions.filter(row => row.kind === 'submit');
  const problems = tests.map(testProblem);
  const textReady = [impact, remediation, prevention].every(value => value.trim().length >= MIN_TEXT);
  const evaluating = latest?.status === 'queued' || latest?.status === 'running';
  const send = useMutation({
    mutationFn: () => resolve(session.id, {
      impact_assessment: impact.trim(), remediation: remediation.trim(), prevention: prevention.trim(),
      regression_tests: tests.map(test => ({ name: test.name.trim(), input: JSON.parse(test.input), expected: JSON.parse(test.expected) })),
      ...(submissionId ? { submission_id: submissionId } : {}),
    }),
    onSuccess: () => { toast.success('Resolution filed. Your regression tests are running.'); onChanged(); },
    onError: error => toast.error(error.message),
  });
  const retry = useMutation({ mutationFn: (id: string) => retryResolution(id), onSuccess: onChanged, onError: error => toast.error(error.message) });
  const update = (index: number, field: keyof DraftTest, value: string) => setTests(previous => previous.map((test, row) => row === index ? { ...test, [field]: value } : test));
  return <div className="incident-resolution">
    <section className="surface">
      <div className="surface-heading"><h2><Stethoscope size={16} /> 1 · Root-cause diagnosis</h2>{payload.diagnosis.latest && <span className="small-tag">REVISION {payload.diagnosis.latest.revision} · {score(payload.diagnosis.latest.score)}/100</span>}</div>
      <p className="muted">Required before you submit a fix. Describe the failing invariant, the component, and how you reproduced it.</p>
      {closed ? <p className="muted">This session is closed.</p> : <DiagnosisPanel problem={problem} language={problem.languages[0]} incidentSessionId={session.id} onSubmitted={onChanged} />}
    </section>
    {latest && <section className="surface">
      <div className="surface-heading"><h2><ClipboardList size={16} /> Latest evaluation</h2><span className="muted">{dateLabel(latest.created_at)}</span></div>
      {evaluating ? <div className="results-empty" role="status"><LoaderCircle size={20} className="spin" /><strong>Evaluating your resolution…</strong><p>Your regression tests run against the correct behaviour and the deployed defect.</p></div>
        : latest.status === 'error' ? <div className="inline-error"><span>{latest.error}</span> <button className="button secondary small" disabled={retry.isPending} onClick={() => retry.mutate(latest.id)}><RotateCcw size={13} />Retry evaluation</button></div>
          : <ResolutionScore resolution={latest} weights={payload.incident.weights} />}
    </section>}
    <section className="surface">
      <div className="surface-heading"><h2><Send size={16} /> 2 · Resolution report</h2></div>
      {closed ? <p className="muted">This incident is resolved. Start a new investigation from the incident page to practise it again.</p> : <form className="resolution-form" onSubmit={event => { event.preventDefault(); send.mutate(); }}>
        <label>Impact assessment<textarea value={impact} maxLength={6000} rows={4} onChange={event => setImpact(event.target.value)} placeholder="Who was affected, how many, for how long, and what it cost." /></label>
        <label>Remediation<textarea value={remediation} maxLength={6000} rows={4} onChange={event => setRemediation(event.target.value)} placeholder="What you changed to stop the failure, and how you repair the damage already done." /></label>
        <label>Prevention<textarea value={prevention} maxLength={6000} rows={4} onChange={event => setPrevention(event.target.value)} placeholder="Tests, alerts, guardrails, or process changes that stop it from recurring." /></label>
        <fieldset className="regression-editor"><legend>Regression tests <span className="muted">({tests.length}/{MAX_TESTS}) · each must pass on correct behaviour and fail on the deployed defect</span></legend>
          {tests.map((test, index) => <div key={index} className="regression-test">
            <div className="regression-test-head"><input aria-label={`Name of regression test ${index + 1}`} value={test.name} maxLength={120} onChange={event => update(index, 'name', event.target.value)} />
              <button type="button" className="icon-button" aria-label={`Remove regression test ${index + 1}`} onClick={() => setTests(previous => previous.filter((_, row) => row !== index))}><Trash2 size={14} /></button></div>
            <div className="regression-test-body">
              <label>Input (JSON)<textarea className="mono" rows={4} value={test.input} onChange={event => update(index, 'input', event.target.value)} /></label>
              <label>Expected output (JSON)<textarea className="mono" rows={4} value={test.expected} onChange={event => update(index, 'expected', event.target.value)} /></label>
            </div>
            {problems[index] && <p className="field-error">{problems[index]}</p>}
          </div>)}
          <button type="button" className="button secondary small" disabled={tests.length >= MAX_TESTS} onClick={() => setTests(previous => [...previous, { name: `Regression ${previous.length + 1}`, input: '{\n  \n}', expected: '' }])}><Plus size={13} />Add regression test</button>
        </fieldset>
        <label>Fix to link <span className="muted">(optional; the best full submission in this session counts toward fix correctness)</span>
          <select value={submissionId} onChange={event => setSubmissionId(event.target.value)}>
            <option value="">No specific submission</option>
            {fixes.map(row => <option key={row.id} value={row.id}>{statusNames[row.status]} · {dateLabel(row.created_at)} · {row.id.slice(0, 8)}</option>)}
          </select></label>
        {!payload.diagnosis.submitted && <p className="field-error">Submit your diagnosis above before filing the resolution.</p>}
        <div className="resolution-actions"><span className="muted">Write at least {MIN_TEXT} characters in each section.</span>
          <button className="button primary" disabled={send.isPending || evaluating || !textReady || problems.some(Boolean) || !payload.diagnosis.submitted}>{send.isPending ? <LoaderCircle size={14} className="spin" /> : <Send size={14} />}File resolution</button></div>
      </form>}
    </section>
    {resolutions.length > 1 && <section className="surface"><div className="surface-heading"><h2>Earlier resolutions</h2></div>
      {resolutions.slice(1).map(row => <details key={row.id} className="scenario-card"><summary><strong>{score(row.score)}/100</strong><span>{row.status} · {dateLabel(row.created_at)}</span></summary>
        {row.status === 'evaluated' && <ResolutionScore resolution={row} weights={payload.incident.weights} />}</details>)}
    </section>}
  </div>;
}
