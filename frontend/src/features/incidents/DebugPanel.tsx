import { Bot, FileCode2, LoaderCircle, LockKeyhole, Play, RotateCcw, Send, Terminal } from 'lucide-react';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError, post } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { languageNames, pending } from '../../lib/constants';
import { ErrorState, Loading } from '../../components/ui';
import Results from '../../components/Results';
import AssistantPanel from '../assistant/AssistantPanel';
import ExplainFixPanel from '../diagnosis/ExplainFixPanel';
import { useDiagnosisStatus } from '../diagnosis/api';
import type { Language, Submission } from '../../types';
import type { SessionPayload } from './types';

const CodeEditor = lazy(() => import('../../components/CodeEditor'));

function readDrafts(key: string): Partial<Record<Language, string>> {
  try {
    const data = JSON.parse(localStorage.getItem(key) || '{}');
    return Object.fromEntries(Object.entries(data).filter(([name, value]) => name in languageNames && typeof value === 'string'));
  } catch { return {}; }
}

export default function DebugPanel({ payload, onNeedDiagnosis, onChanged }: {
  payload: SessionPayload; onNeedDiagnosis: () => void; onChanged: () => void;
}) {
  const { user } = useAuth();
  const client = useQueryClient();
  const { problem, session } = payload;
  const draftKey = `leetbug.incident-drafts.v1:${user?.id ?? 'guest'}:${session.id}`;
  const [language, setLanguage] = useState<Language>(problem.languages[0]);
  const [drafts, setDrafts] = useState(() => readDrafts(draftKey));
  const [resultId, setResultId] = useState<string | null>(payload.submissions[0]?.id ?? null);
  const handled = useRef<string | null>(payload.submissions[0]?.id ?? null);
  const code = drafts[language] ?? problem.starters[language] ?? '';
  const closed = session.status !== 'active';
  const diagnosis = useDiagnosisStatus(problem.slug, { enabled: !closed, incidentSessionId: session.id });
  const diagnosed = payload.diagnosis.submitted || diagnosis.submitted;
  const result = useQuery({ queryKey: ['submission', resultId], queryFn: () => api<Submission>(`/submissions/${resultId}`), enabled: !!resultId,
    refetchInterval: query => query.state.error ? false : pending(query.state.data?.status) || !query.state.data ? 800 : false });
  const busy = pending(result.data?.status);
  const latestDrafts = useRef(drafts);
  useEffect(() => {
    latestDrafts.current = drafts;
    const timer = setTimeout(() => { try { localStorage.setItem(draftKey, JSON.stringify(drafts)); } catch { /* Editing works without storage. */ } }, 300);
    return () => clearTimeout(timer);
  }, [draftKey, drafts]);
  // Switching tabs unmounts the editor; flush the newest draft so no keystrokes are lost.
  useEffect(() => () => { try { localStorage.setItem(draftKey, JSON.stringify(latestDrafts.current)); } catch { /* Editing works without storage. */ } }, [draftKey]);
  useEffect(() => {
    const row = result.data;
    if (!row || pending(row.status) || handled.current === row.id) return;
    handled.current = row.id;
    onChanged();
  }, [result.data, onChanged]);
  const submit = useMutation({
    mutationFn: (kind: 'run' | 'submit') => post<Submission>('/submissions', {
      problem_id: problem.id, language, mode: 'manual', kind, code, incident_session_id: session.id }),
    onSuccess: row => { client.setQueryData(['submission', row.id], row); setResultId(row.id); },
    onError: error => {
      if (error instanceof ApiError && error.status === 428) onNeedDiagnosis();
      toast.error(error.message);
    },
  });
  const blocked = busy || submit.isPending || closed;
  const testsByName = new Map(problem.public_tests.map(test => [test.name, test]));
  return <div className="incident-debug">
    <aside className="incident-debug-side">
      <section className="surface">
        <div className="surface-heading"><h2>Reproduction scenarios</h2><Terminal size={16} /></div>
        <p className="muted">Run reproduction executes these public scenarios. Hidden regression cases run when you submit a fix.</p>
        {payload.incident.scenarios.map(scenario => <details key={scenario.id} className="scenario-card">
          <summary><strong>{scenario.name}</strong>{scenario.description && <span>{scenario.description}</span>}</summary>
          {scenario.tests.map(name => {
            const test = testsByName.get(name);
            return test ? <div key={name} className="example-card"><strong>{name}</strong><label>Input</label><pre>{JSON.stringify(test.input, null, 2)}</pre><label>Expected</label><pre>{JSON.stringify(test.expected, null, 2)}</pre></div> : null;
          })}
        </details>)}
        <p className="hidden-note"><LockKeyhole size={13} />{problem.hidden_test_count} hidden regression cases check that the fix holds beyond the reproduction.</p>
      </section>
      <details className="surface incident-assistant">
        <summary><Bot size={16} />Ask the debugging assistant</summary>
        <AssistantPanel problem={problem} language={language} code={code} latestSubmission={result.data} incidentSessionId={session.id} />
      </details>
    </aside>
    <section className="editor-panel incident-editor-panel" aria-label="Incident code editor">
      <div className="editor-toolbar">
        <div className="editor-filename"><FileCode2 size={13} /><span>{problem.title}</span></div>
        <div className="editor-tools">
          <select aria-label="Editor language" value={language} disabled={blocked} onChange={event => setLanguage(event.target.value as Language)}>{problem.languages.map(value => <option key={value} value={value}>{languageNames[value]}</option>)}</select>
          <button className="icon-button" aria-label="Reset code to the deployed version" disabled={blocked} onClick={() => { if (window.confirm('Reset this language to the deployed (buggy) code? Your draft will be replaced.')) setDrafts(previous => ({ ...previous, [language]: problem.starters[language] || '' })); }}><RotateCcw size={15} /></button>
        </div>
      </div>
      <div className="incident-editor"><Suspense fallback={<Loading label="Opening editor…" />}><CodeEditor language={language} value={code} readOnly={blocked} onChange={value => setDrafts(previous => ({ ...previous, [language]: value }))} /></Suspense></div>
      <div className="run-toolbar">
        <span>{closed ? 'This session is closed. Start a new investigation to keep debugging.' : !diagnosed ? 'Record your root-cause diagnosis (Resolution tab) before submitting a fix.' : 'Reproduce, fix, then verify against the hidden regression cases.'}</span>
        <div>
          <button className="button secondary small" disabled={blocked} onClick={() => submit.mutate('run')}><Play size={13} />Run reproduction</button>
          <button className="button primary small" disabled={blocked || !diagnosed} title={!diagnosed ? 'Submit your diagnosis first' : undefined} onClick={() => submit.mutate('submit')}>{busy || submit.isPending ? <LoaderCircle size={14} className="spin" /> : <Send size={13} />}Submit fix</button>
        </div>
      </div>
      <div className="result-panel"><div className="result-panel-header"><span><Terminal size={14} />Test results</span></div>
        {result.isError ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : <><Results submission={result.data} context="incident" />
          {result.data?.status === 'passed' && result.data.kind === 'submit' && result.data.problem_id === problem.id && <ExplainFixPanel problem={problem} submission={result.data} incidentSessionId={session.id} />}</>}
      </div>
    </section>
  </div>;
}
