import { ArrowLeft, Bot, BookOpen, Check, CheckCircle2, Circle, FileCode2, Flag, Lightbulb, LoaderCircle, LockKeyhole, Play, RotateCcw, Send, Stethoscope, Terminal, Timer, X } from 'lucide-react';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { api, ApiError, post } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { categories, languageNames, pending } from '../../lib/constants';
import { Difficulty, ErrorState, Loading, SignInCard } from '../../components/ui';
import Results from '../../components/Results';
import Modal from '../../components/Modal';
import DiagnosisPanel from '../diagnosis/DiagnosisPanel';
import ExplainFixPanel from '../diagnosis/ExplainFixPanel';
import { useDiagnosisStatus } from '../diagnosis/api';
import AssistantPanel from '../assistant/AssistantPanel';
import type { Category, Hint, Language, ProblemDetail, Submission } from '../../types';
import { finishSession, getSession } from './api';
import { clock } from './format';
import type { AssessmentSessionView, SessionChallenge } from './types';
import './assessments.css';

const CodeEditor = lazy(() => import('../../components/CodeEditor'));
const fileNames: Record<Language, string> = { python: 'solution.py', javascript: 'solution.js', java: 'Solution.java', cpp: 'solution.cpp', go: 'solution.go' };

export default function AssessmentRunner() {
  const { id = '' } = useParams();
  const { user, loading } = useAuth();
  const query = useQuery({ queryKey: ['assessment-session', id], queryFn: () => getSession(id), enabled: !!user,
    refetchInterval: 30_000, refetchOnWindowFocus: true });
  if (loading) return <Loading />;
  if (!user) return <div className="page"><SignInCard title="Sign in to continue your assessment" /></div>;
  if (query.isPending) return <Loading label="Opening your session…" />;
  if (query.isError) return <div className="page"><ErrorState error={query.error} retry={() => void query.refetch()} /></div>;
  // The server decides when a session ends; a finished or expired session continues on the report page.
  if (query.data.status !== 'active' || query.data.viewer !== 'candidate') return <Navigate to={`/assessment-sessions/${id}/report`} replace />;
  return <Runner session={query.data} fetchedAt={query.dataUpdatedAt} refetch={query.refetch} />;
}

/** Seconds left, counted locally from the server's remaining time at fetch (immune to client clock skew). */
function useRemaining(serverRemaining: number, fetchedAt: number) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  return now === null ? serverRemaining : Math.max(0, serverRemaining - Math.floor((now - fetchedAt) / 1000));
}

function Runner({ session, fetchedAt, refetch }: { session: AssessmentSessionView; fetchedAt: number; refetch: () => Promise<unknown> }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [confirming, setConfirming] = useState(false);
  const index = Math.min(Math.max(Number(params.get('challenge')) || 1, 1), session.challenges.length) - 1;
  const challenge = session.challenges[index];
  const remaining = useRemaining(session.remaining_seconds, fetchedAt);
  const expired = remaining <= 0;
  useEffect(() => { if (expired) void refetch(); }, [expired, refetch]);
  const finish = useMutation({ mutationFn: () => finishSession(session.id), onSuccess: () => {
    void client.invalidateQueries({ queryKey: ['assessment-history'] });
    void client.invalidateQueries({ queryKey: ['assessments'] });
    navigate(`/assessment-sessions/${session.id}/report`, { replace: true });
  }, onError: error => { toast.error(error.message); void refetch(); } });
  const solved = session.challenges.filter(row => row.status === 'solved').length;
  return <div className="asm-runner">
    <header className="asm-runner-bar">
      <div className="asm-runner-title"><Link to={`/assessments/${session.assessment.slug}`} className="text-link" aria-label="Assessment details"><ArrowLeft size={14} /></Link><div><strong>{session.assessment.title}</strong><span>{solved} of {session.challenges.length} solved</span></div></div>
      <nav className="asm-challenge-nav" aria-label="Challenges">{session.challenges.map((row, position) => <button key={row.problem_id} aria-current={position === index ? 'step' : undefined} className={`asm-step ${row.status}`} title={`${row.title} — ${row.status.replace('_', ' ')}`} onClick={() => setParams({ challenge: String(position + 1) }, { replace: true })}>{row.status === 'solved' ? <CheckCircle2 size={13} /> : <Circle size={13} />}{position + 1}</button>)}</nav>
      <div className={`asm-timer ${remaining < 300 ? 'urgent' : ''}`} role="timer" aria-label={`Time remaining ${clock(remaining)}`}><Timer size={14} />{clock(remaining)}</div>
      <button className="button primary small" onClick={() => setConfirming(true)}><Flag size={13} />Finish</button>
    </header>
    {challenge?.problem ? <ChallengeWorkspace key={challenge.problem_id} session={session} challenge={challenge} problem={challenge.problem} onChanged={() => void refetch()} />
      : <p className="inline-error">This challenge is unavailable. Reload the session.</p>}
    {confirming && <Modal label="Finish assessment" onDismiss={() => setConfirming(false)}>
      <div className="modal-heading"><span><Flag size={19} />Finish the assessment?</span><button autoFocus className="icon-button" aria-label="Close" onClick={() => setConfirming(false)}><X size={18} /></button></div>
      <p className="asm-modal-text">You solved {solved} of {session.challenges.length} challenges. After finishing you cannot change any work; unfinished challenges score zero.</p>
      {session.pending_evaluations > 0 && <p className="asm-modal-text">{session.pending_evaluations} evaluation(s) are still running. They count if they finish within five minutes.</p>}
      <div className="asm-modal-actions"><button className="button secondary" onClick={() => setConfirming(false)}>Keep working</button><button className="button primary" disabled={finish.isPending} onClick={() => finish.mutate()}>{finish.isPending && <LoaderCircle size={14} className="spin" />}Finish and score</button></div>
    </Modal>}
  </div>;
}

function readDraft(key: string): Partial<Record<Language, string>> {
  try {
    const data = JSON.parse(localStorage.getItem(key) || '{}');
    return Object.fromEntries(Object.entries(data).filter(([name, value]) => name in languageNames && typeof value === 'string'));
  } catch { return {}; }
}

function ChallengeWorkspace({ session, challenge, problem, onChanged }: {
  session: AssessmentSessionView; challenge: SessionChallenge; problem: ProblemDetail; onChanged: () => void;
}) {
  const client = useQueryClient();
  const policy = session.assessment.assistance_policy;
  const configuration = session.assessment.configuration;
  const draftKey = `leetbug.assessment.v1:${session.id}:${problem.id}`;
  const latest = challenge.submissions[0];
  const [language, setLanguage] = useState<Language>(latest && problem.languages.includes(latest.language) ? latest.language : problem.languages[0]);
  const [drafts, setDrafts] = useState(() => readDraft(draftKey));
  const [tab, setTab] = useState<'challenge' | 'diagnosis' | 'assistant'>(configuration.diagnosis_required && !challenge.diagnosis_submitted ? 'diagnosis' : 'challenge');
  const [resultId, setResultId] = useState<string | null>(latest?.id ?? null);
  const handled = useRef<string | null>(latest && !pending(latest.status) ? latest.id : null);
  const code = drafts[language] ?? problem.starters[language] ?? '';
  const result = useQuery({ queryKey: ['submission', resultId], queryFn: () => api<Submission>(`/submissions/${resultId}`), enabled: !!resultId,
    refetchInterval: query => query.state.error ? false : pending(query.state.data?.status) || !query.state.data ? 800 : false });
  const diagnosis = useDiagnosisStatus(problem.slug, { enabled: true, assessmentSessionId: session.id });
  const needsDiagnosis = configuration.diagnosis_required && !(challenge.diagnosis_submitted || diagnosis.submitted);
  const outOfAttempts = challenge.max_attempts != null && challenge.submissions_used >= challenge.max_attempts;
  const busy = pending(result.data?.status) || (!!resultId && result.isPending);
  useEffect(() => {
    const timer = setTimeout(() => { try { localStorage.setItem(draftKey, JSON.stringify(drafts)); } catch { /* Editing works without storage. */ } }, 300);
    return () => clearTimeout(timer);
  }, [draftKey, drafts]);
  useEffect(() => {
    const row = result.data;
    if (!row || pending(row.status) || handled.current === row.id) return;
    handled.current = row.id;
    onChanged();
  }, [result.data, onChanged]);
  const submit = useMutation({ mutationFn: (kind: 'run' | 'submit') => post<Submission>('/submissions', {
    problem_id: problem.id, language, mode: 'manual', kind, code, assessment_session_id: session.id,
  }), onSuccess: row => { handled.current = null; setResultId(row.id); client.setQueryData(['submission', row.id], row); onChanged(); },
  onError: error => {
    if (error instanceof ApiError && error.status === 428) setTab('diagnosis');
    toast.error(error.message);
    if (error instanceof ApiError && error.status === 409) onChanged();
  } });
  const blocked = busy || submit.isPending;
  const accepted = result.data?.status === 'passed' && result.data.kind === 'submit' && result.data.problem_id === problem.id;
  const category = categories[problem.category as Category];
  return <div className="workspace-grid asm-workspace">
    <section className="problem-panel" aria-label="Challenge context">
      <div className="panel-tabs"><button className={tab === 'challenge' ? 'active' : ''} onClick={() => setTab('challenge')}><BookOpen size={14} />Challenge</button>
        <button className={tab === 'diagnosis' ? 'active' : ''} onClick={() => setTab('diagnosis')}><Stethoscope size={14} />Diagnosis{needsDiagnosis && <span className="tab-dot" aria-label="Diagnosis required" />}</button>
        {policy.ai !== 'disabled' && <button className={tab === 'assistant' ? 'active' : ''} onClick={() => setTab('assistant')}><Bot size={14} />Assistant</button>}</div>
      <div className="problem-panel-content">
        {tab === 'diagnosis' ? <DiagnosisPanel problem={problem} language={language} assessmentSessionId={session.id} onSubmitted={() => { onChanged(); void client.invalidateQueries({ queryKey: ['diagnosis', problem.slug] }); }} />
          : tab === 'assistant' && policy.ai !== 'disabled' ? <AssistantPanel problem={problem} language={language} code={code} latestSubmission={result.data} assessmentSessionId={session.id} />
          : <>
            <div className="case-meta">{category && <span className={`category-pill ${category.color}`}>{category.short}</span>}<Difficulty value={problem.difficulty} /><span className="muted">Challenge {challenge.position} of {session.challenges.length}</span></div>
            <h1>{problem.title}</h1><p className="problem-description">{problem.description}</p>
            <div className="problem-context-label"><span />THE EXPECTED BEHAVIOR</div>
            <ul className="requirements">{problem.requirements.map(requirement => <li key={requirement}>{requirement}</li>)}</ul>
            <div className="problem-context-label"><span />PUBLIC TEST CASES</div>
            {problem.public_tests.map((test, position) => <div className="example-card" key={test.name}><strong><span>{String(position + 1).padStart(2, '0')}</span>{test.name}</strong><label>Input</label><pre>{JSON.stringify(test.input, null, 2)}</pre><label>Expected output</label><pre>{JSON.stringify(test.expected, null, 2)}</pre></div>)}
            <p className="hidden-note"><LockKeyhole size={13} />{problem.hidden_test_count} hidden cases check how well your fix generalizes. Solutions stay locked during the assessment.</p>
          </>}
      </div>
      {policy.hints !== 'disabled' && <HintBar problem={problem} language={language} sessionId={session.id} restricted={policy.hints === 'restricted'} />}
    </section>
    <section className="editor-panel" aria-label="Assessment editor">
      <div className="editor-toolbar"><span className="asm-attempts">{challenge.max_attempts ? `${challenge.submissions_used} of ${challenge.max_attempts} submissions used` : `${challenge.submissions_used} submissions`}</span>
        <div className="editor-tools"><select aria-label="Editor language" value={language} disabled={blocked} onChange={event => setLanguage(event.target.value as Language)}>{problem.languages.map(value => <option key={value} value={value}>{languageNames[value]}</option>)}</select>
          <button className="icon-button" aria-label="Reset code to starter" disabled={blocked} onClick={() => { if (window.confirm('Reset this language to the original buggy code? Your current draft will be replaced.')) setDrafts(previous => ({ ...previous, [language]: problem.starters[language] || '' })); }}><RotateCcw size={15} /></button></div></div>
      <div className="editor-filename"><FileCode2 size={13} /><span>{fileNames[language]}</span><span className="editor-readiness"><span />{blocked ? 'Evaluating' : 'Draft saved on this device'}</span></div>
      <div className="monaco-wrap"><Suspense fallback={<Loading label="Opening editor…" />}><CodeEditor language={language} value={code} readOnly={blocked} onChange={value => setDrafts(previous => ({ ...previous, [language]: value }))} /></Suspense></div>
      <div className="run-toolbar"><span>{needsDiagnosis ? <><Stethoscope size={13} />Diagnose the root cause to unlock Submit.</> : outOfAttempts ? <><LockKeyhole size={13} />No submissions left for this challenge.</> : <><Terminal size={13} />Run the public tests, then submit.</>}</span>
        <div><button className="button secondary small" disabled={blocked} onClick={() => submit.mutate('run')}><Play size={13} />Run code</button>
          <button className="button primary small" title={needsDiagnosis ? 'Submit your diagnosis first' : undefined} disabled={blocked || needsDiagnosis || outOfAttempts} onClick={() => submit.mutate('submit')}>{blocked ? <LoaderCircle size={14} className="spin" /> : <Send size={13} />}Submit fix</button></div></div>
      <div className="result-panel"><div className="result-panel-header"><span><Terminal size={14} />Test results</span></div>
        {result.isError ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : <Results submission={result.data} context="assessment" />}
        {accepted && <div className="asm-accepted"><p className="success-note asm-note"><Check size={15} />All tests passed. Your fix is recorded for this assessment.</p>
          <ExplainFixPanel problem={problem} submission={result.data!} assessmentSessionId={session.id} required={configuration.explanation_required} /></div>}
      </div>
    </section>
  </div>;
}

function HintBar({ problem, language, sessionId, restricted }: { problem: ProblemDetail; language: Language; sessionId: string; restricted: boolean }) {
  const [hintId, setHintId] = useState<string | null>(null);
  const hint = useQuery({ queryKey: ['hint', hintId], queryFn: () => api<Hint>(`/hints/${hintId}`), enabled: !!hintId,
    refetchInterval: query => query.state.error ? false : pending(query.state.data?.status) || !query.state.data ? 1000 : false });
  const request = useMutation({ mutationFn: () => post<Hint>(`/problems/${problem.slug}/hints`, { language, assessment_session_id: sessionId }),
    onSuccess: row => setHintId(row.id), onError: error => toast.error(error.message) });
  const text = hint.data?.status === 'completed' ? hint.data.text : hint.data?.status === 'error' ? hint.data.error : null;
  return <div className="asm-hint">
    <div className="hint-footer"><Lightbulb size={16} /><div><strong>{restricted ? 'One conceptual hint' : 'Progressive hints'}</strong><span>{problem.hints_unlocked ? 'Hint use is recorded in your report.' : 'Hints unlock after unsuccessful runs.'}</span></div>
      <button className="button secondary small" disabled={!problem.hints_unlocked || request.isPending || pending(hint.data?.status) || (restricted && !!hint.data)} onClick={() => request.mutate()}>{request.isPending ? <LoaderCircle size={14} className="spin" /> : hintId && !restricted ? 'Next hint' : 'Get hint'}</button></div>
    {hintId && <div className="asm-hint-text" aria-live="polite">{text ?? <LoaderCircle size={14} className="spin" />}</div>}
  </div>;
}
