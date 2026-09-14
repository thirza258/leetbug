import { ArrowLeft, ArrowRight, BookOpen, Bookmark, Check, ChevronRight, Code2, Copy, FileCode2, History, Lightbulb, LoaderCircle, LockKeyhole, MessageSquare, Play, RotateCcw, Send, Share2, Sparkles, Terminal, X } from 'lucide-react';
import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { api, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { categories, languageNames, pending } from '../lib/constants';
import { Difficulty, ErrorState, Loading, StatusBadge } from '../components/ui';
import Results from '../components/Results';
import type { Hint, Language, Meta, Mode, Page, ProblemDetail, Solutions, Submission } from '../types';

const CodeEditor = lazy(() => import('../components/CodeEditor'));
export default function Workspace() {
  const { slug = '' } = useParams();
  const { user } = useAuth();
  const query = useQuery({ queryKey: ['problem', slug, user?.id], queryFn: () => api<ProblemDetail>(`/problems/${slug}`) });
  if (query.isPending) return <Loading />;
  if (query.isError) return <div className="page"><ErrorState error={query.error} retry={() => void query.refetch()} /></div>;
  return <WorkspaceContent key={`${slug}:${user?.id ?? 'guest'}`} problem={query.data} />;
}

function readDraft(key: string): Partial<Record<Language, string>> {
  try {
    const data = JSON.parse(localStorage.getItem(key) || '{}');
    return Object.fromEntries(Object.entries(data).filter(([key, value]) => key in languageNames && typeof value === 'string'));
  } catch { return {}; }
}

function WorkspaceContent({ problem }: { problem: ProblemDetail }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const draftKey = `leetbug.drafts.v1:${user?.id || 'guest'}:${problem.slug}`;
  const [language, setLanguage] = useState<Language>(problem.languages[0]);
  const [drafts, setDrafts] = useState(() => readDraft(draftKey));
  const [mode, setMode] = useState<Mode>('manual');
  const [prompt, setPrompt] = useState('');
  const [tab, setTab] = useState<'description' | 'solutions' | 'history'>('description');
  const [hintId, setHintId] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [resultId, setResultId] = useState<string | null>(params.get('submission'));
  const handled = useRef<string | null>(null);
  const restoreId = useRef(params.get('submission'));
  const code = drafts[language] ?? problem.starters[language] ?? '';
  const meta = useQuery({ queryKey: ['meta'], queryFn: () => api<Meta>('/meta') });
  const result = useQuery({ queryKey: ['submission', resultId], queryFn: () => api<Submission>(`/submissions/${resultId}`),
    enabled: !!resultId && !!user, refetchInterval: query => pending(query.state.data?.status) || !query.state.data ? 800 : false });
  const busy = pending(result.data?.status) || (!!resultId && result.isPending && !!user);
  const solved = problem.status === 'solved' || (result.data?.status === 'passed' && result.data.kind === 'submit');
  const solutions = useQuery({ queryKey: ['solutions', problem.slug, user?.id],
    queryFn: () => api<Solutions>(`/problems/${problem.slug}/solutions`), enabled: tab === 'solutions' && !!user && solved });
  const history = useQuery({ queryKey: ['submissions', problem.id, user?.id],
    queryFn: () => api<Page<Submission>>(`/submissions?problem_id=${problem.id}&limit=30`), enabled: tab === 'history' && !!user });
  const hint = useQuery({ queryKey: ['hint', hintId], queryFn: () => api<Hint>(`/hints/${hintId}`), enabled: !!hintId,
    refetchInterval: query => pending(query.state.data?.status) || !query.state.data ? 1000 : false });
  useEffect(() => {
    const timer = setTimeout(() => { try { localStorage.setItem(draftKey, JSON.stringify(drafts)); } catch { /* Editing remains available without storage. */ } }, 300);
    return () => clearTimeout(timer);
  }, [draftKey, drafts]);
  useEffect(() => {
    const row = result.data;
    if (!row || row.problem_id !== problem.id) return;
    if (restoreId.current === row.id) {
      restoreId.current = null;
      // Synchronize a persisted attempt selected from the history with the editor.
      setLanguage(row.language); setMode(row.mode); setPrompt(row.prompt);
      setDrafts(previous => ({ ...previous, [row.language]: row.generated_code || row.code }));
    }
    if (pending(row.status) || handled.current === row.id) return;
    handled.current = row.id;
    if (row.generated_code) setDrafts(previous => ({ ...previous, [row.language]: row.generated_code! }));
    void client.invalidateQueries({ queryKey: ['problem', problem.slug] });
    void client.invalidateQueries({ queryKey: ['submissions'] });
    void client.invalidateQueries({ queryKey: ['stats'] });
    void client.invalidateQueries({ queryKey: ['problems'] });
  }, [result.data, problem.id, problem.slug, client]);
  const submit = useMutation({ mutationFn: (kind: 'run' | 'submit') => post<Submission>('/submissions', {
    problem_id: problem.id, language, mode, kind, code, prompt: mode === 'ai' ? prompt : '',
  }), onSuccess: row => {
    handled.current = null; restoreId.current = null; setResultId(row.id);
    client.setQueryData(['submission', row.id], row); setParams({ submission: row.id }, { replace: true });
  }, onError: error => toast.error(error.message) });
  const requestHint = useMutation({ mutationFn: () => post<Hint>(`/problems/${problem.slug}/hints`, { language }),
    onSuccess: row => { setHintId(row.id); client.setQueryData(['hint', row.id], row); setShowHint(true); },
    onError: error => toast.error(error.message) });
  function run(kind: 'run' | 'submit') {
    if (!user) { navigate(`/login?next=${encodeURIComponent(`/problems/${problem.slug}`)}`); return; }
    submit.mutate(kind);
  }
  async function bookmark() {
    if (!user) { navigate('/login'); return; }
    try { await post(`/problems/${problem.slug}/bookmark`); await client.invalidateQueries({ queryKey: ['problem', problem.slug] }); }
    catch (error) { toast.error((error as Error).message); }
  }
  async function share() {
    if (!result.data) return;
    try { const value = await post<{ shared: boolean }>(`/submissions/${result.data.id}/share`); toast.success(value.shared ? 'Your fix is now shared with other solvers.' : 'Your fix is private again.'); await client.invalidateQueries({ queryKey: ['submission', resultId] }); await client.invalidateQueries({ queryKey: ['solutions', problem.slug] }); }
    catch (error) { toast.error((error as Error).message); }
  }
  const blocked = busy || submit.isPending;
  return <div className="workspace-page"><div className="workspace-heading"><Link to="/" className="text-link"><ArrowLeft size={15} /> Library</Link><ChevronRight size={14} /><span>Case {String(problem.id).padStart(2, '0')}</span><div className="workspace-heading-right"><span className="draft-saved"><span />Draft saved locally</span><button className={`icon-button ${problem.bookmarked ? 'purple' : ''}`} aria-label="Save case study" onClick={() => void bookmark()}><Bookmark size={16} fill={problem.bookmarked ? 'currentColor' : 'none'} /></button></div></div>
    <div className="workspace-grid"><section className="problem-panel" aria-label="Problem context"><div className="panel-tabs"><button className={tab === 'description' ? 'active' : ''} onClick={() => setTab('description')}><BookOpen size={14} />Description</button><button className={tab === 'solutions' ? 'active' : ''} onClick={() => setTab('solutions')}>{solved ? <Check size={14} /> : <LockKeyhole size={13} />}Solutions</button><button className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}><History size={14} />Attempts</button></div>
      <div className="problem-panel-content">{tab === 'description' ? <><div className="case-meta"><span className={`category-pill ${categories[problem.category].color}`}>{categories[problem.category].short}</span><Difficulty value={problem.difficulty} /></div><h1>{problem.title}</h1><p className="problem-description">{problem.description}</p><div className="problem-context-label"><span />THE EXPECTED BEHAVIOR</div><ul className="requirements">{problem.requirements.map(requirement => <li key={requirement}>{requirement}</li>)}</ul><div className="problem-context-label"><span />PUBLIC TEST CASES</div>{problem.public_tests.map((test, index) => <div className="example-card" key={test.name}><strong><span>{String(index + 1).padStart(2, '0')}</span>{test.name}</strong><label>Input</label><pre>{JSON.stringify(test.input, null, 2)}</pre><label>Expected output</label><pre>{JSON.stringify(test.expected, null, 2)}</pre>{test.assertions.length > 0 && <p className="state-note"><Check size={12} />Includes {test.assertions.length} state assertion{test.assertions.length > 1 ? 's' : ''}</p>}</div>)}<p className="hidden-note"><LockKeyhole size={13} />{problem.hidden_test_count} hidden cases check how well your fix generalizes.</p><div className="problem-topic-tags">{problem.tags.map(tag => <Link to={`/?tag=${tag}`} key={tag}>#{tag}</Link>)}</div><Link className="discussion-link" to={`/discussions?problem_id=${problem.id}`}><MessageSquare size={16} />Talk through this problem<ArrowUpRightIcon /></Link></> : tab === 'solutions' ? !solved ? <div className="locked-panel"><LockKeyhole size={28} /><h3>Earn your “aha!” moment.</h3><p>Pass all public and hidden tests with Submit Fix to unlock the optimal solution and shared community fixes.</p></div> : solutions.isPending ? <Loading label="Opening solutions…" /> : solutions.isError ? <ErrorState error={solutions.error} /> : <><span className="eyebrow green">FIX ACCEPTED</span><h2>Behind the fix</h2><p className="problem-description">{solutions.data.explanation}</p><div className="solution-code"><div><FileCode2 size={14} />{languageNames[language]}<button className="icon-button" aria-label="Copy optimal solution" onClick={() => { navigator.clipboard.writeText(solutions.data.solutions[language] || '').then(() => toast.success('Solution copied.')).catch(() => toast.error('Clipboard is unavailable.')); }}><Copy size={13} /></button></div><pre>{solutions.data.solutions[language]}</pre></div><h3 className="community-solution-heading">From the community</h3>{solutions.data.community.length ? solutions.data.community.map(row => <details className="community-solution" key={row.id}><summary>@{row.username}<span>{languageNames[row.language]} · {row.mode === 'ai' ? `${row.prompt_words} words` : 'Manual'}</span></summary>{row.prompt && <blockquote>{row.prompt}</blockquote>}<pre>{row.code}</pre></details>) : <p className="muted">No shared fixes yet. Share your accepted submission to start the conversation.</p>}</> : !user ? <p className="muted">Sign in to keep a history of your attempts.</p> : history.isPending ? <Loading /> : history.isError ? <ErrorState error={history.error} /> : history.data.items.length ? history.data.items.map(row => <button className="attempt-row" key={row.id} onClick={() => { restoreId.current = row.id; handled.current = null; setResultId(row.id); setParams({ submission: row.id }, { replace: true }); }}><StatusBadge status={row.status} /><span>{languageNames[row.language]} · {row.mode === 'ai' ? 'AI' : 'Manual'} · {row.kind}</span><small>{new Date(row.created_at).toLocaleString()}</small></button>) : <p className="muted">Your first attempt starts here. Run the code to see the bug in action.</p>}
      </div><div className="hint-footer"><Lightbulb size={16} /><div><strong>A nudge in the right direction</strong><span>{problem.hints_unlocked ? 'Grounded in official documentation.' : `Hints unlock after ${meta.data?.hint_failure_threshold ?? 2} unsuccessful runs.`}</span></div><button className="button secondary small" disabled={!user || !problem.hints_unlocked || requestHint.isPending || pending(hint.data?.status)} onClick={() => hintId ? setShowHint(true) : requestHint.mutate()}>{requestHint.isPending ? <LoaderCircle size={14} className="spin" /> : 'Get hint'}</button></div>
    </section>
    <section className="editor-panel" aria-label="Debugging editor"><div className="editor-toolbar"><div className="mode-switch" role="group" aria-label="Resolution mode"><button className={mode === 'manual' ? 'active' : ''} disabled={blocked} onClick={() => setMode('manual')}><Code2 size={15} />Manual</button><button className={mode === 'ai' ? 'active' : ''} disabled={blocked} onClick={() => setMode('ai')}><Sparkles size={14} />AI assist</button></div><div className="editor-tools"><select aria-label="Editor language" value={language} disabled={blocked} onChange={event => setLanguage(event.target.value as Language)}>{problem.languages.map(value => <option key={value} value={value}>{languageNames[value]}</option>)}</select><button className="icon-button" aria-label="Reset code to starter" disabled={blocked} onClick={() => { if (window.confirm('Reset this language to the original buggy code? Your current draft will be replaced.')) setDrafts(previous => ({ ...previous, [language]: problem.starters[language] || '' })); }}><RotateCcw size={15} /></button></div></div>
      {mode === 'ai' && <div className="prompt-panel"><div><span className="eyebrow"><Sparkles size={12} />YOU’RE THE LEAD ENGINEER</span><span className="prompt-word-count">{prompt.trim() ? prompt.trim().split(/\s+/).length : 0} words</span></div><label htmlFor="ai-prompt">Tell your AI what to fix — and why.</label><textarea id="ai-prompt" value={prompt} maxLength={4000} disabled={blocked} onChange={event => setPrompt(event.target.value)} placeholder="Identify the broken assumption, describe the intended behavior, and give a focused instruction…" /><p>{meta.data?.ai_enabled ? `Using ${meta.data.ai_model}. The patch appears in the editor and is evaluated below.` : 'AI fixes need an OpenRouter or Ollama model. Manual mode is ready to use.'}</p></div>}
      <div className="editor-filename"><FileCode2 size={13} /><span>{language === 'java' ? 'Solution.java' : `solution.${{ python: 'py', javascript: 'js', cpp: 'cpp', go: 'go' }[language as Exclude<Language, 'java'>]}`}</span><span className="editor-readiness"><span />{blocked ? 'Evaluating' : 'Ready to debug'}</span></div><div className={`monaco-wrap ${mode === 'ai' ? 'with-prompt' : ''}`}><Suspense fallback={<Loading label="Opening editor…" />}><CodeEditor language={language} value={code} readOnly={blocked} onChange={value => setDrafts(previous => ({ ...previous, [language]: value }))} /></Suspense></div>
      <div className="run-toolbar"><span><Terminal size={13} />{mode === 'ai' ? 'Prompt. Patch. Verify.' : 'Make a change. Test your thinking.'}</span><div><button className="button secondary small" disabled={blocked || (mode === 'ai' && (!meta.data?.ai_enabled || prompt.trim().length < 10))} onClick={() => run('run')}><Play size={13} />Run code</button><button className="button primary small" disabled={blocked || (mode === 'ai' && (!meta.data?.ai_enabled || prompt.trim().length < 10))} onClick={() => run('submit')}>{blocked ? <LoaderCircle size={14} className="spin" /> : <Send size={13} />}Submit fix</button></div></div>
      <div className="result-panel"><div className="result-panel-header"><span><Terminal size={14} />Test results</span>{result.data?.status === 'passed' && result.data.kind === 'submit' && <button className="text-link" onClick={() => void share()}><Share2 size={13} />{result.data.shared ? 'Make private' : 'Share this fix'}</button>}</div>{result.isError ? <ErrorState error={result.error} retry={() => void result.refetch()} /> : result.data?.problem_id && result.data.problem_id !== problem.id ? <p className="inline-error">This submission belongs to a different case study.</p> : <Results submission={result.data} />}</div>
    </section></div>
    {showHint && <div className="modal-backdrop" onClick={() => setShowHint(false)}><section className="modal hint-modal" role="dialog" aria-modal="true" aria-label="Documentation-backed hint" onClick={event => event.stopPropagation()}><div className="modal-heading"><span><Lightbulb size={20} />A little direction</span><button autoFocus className="icon-button" aria-label="Close hint" onClick={() => setShowHint(false)}><X size={18} /></button></div>{hint.isError ? <ErrorState error={hint.error} /> : !hint.data || pending(hint.data.status) ? <Loading label="Finding the right documentation…" /> : hint.data.status === 'error' ? <p className="inline-error">{hint.data.error}</p> : <><span className="eyebrow">HINT {hint.data.level} OF {problem.hints_unlocked ? 3 : 0}</span><p className="hint-text">{hint.data.text}</p><h4>From the official docs</h4>{hint.data.sources.map((source, index) => <details className="hint-source" key={source.url}><summary><span>[{index + 1}]</span>{source.title}</summary><p>{source.excerpt}</p><a href={source.url} target="_blank" rel="noreferrer" className="text-link">Read documentation <ArrowRight size={13} /></a></details>)}<div className="hint-modal-footer"><span>Keep going. You’re building the instinct.</span><button className="button secondary small" disabled={hint.data.level >= 3 || requestHint.isPending} onClick={() => requestHint.mutate()}>Next hint <ArrowRight size={13} /></button></div></>}</section></div>}
  </div>;
}

function ArrowUpRightIcon() { return <ArrowRight size={14} />; }

