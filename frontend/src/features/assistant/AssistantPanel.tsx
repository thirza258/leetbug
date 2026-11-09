import { BookOpen, Bot, Bug, Clock3, ExternalLink, FileSearch, Info, Lightbulb, LoaderCircle, Microscope, Repeat2, Send, ShieldAlert, Stethoscope } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api } from '../../lib/api';
import { ms, pending } from '../../lib/constants';
import { ErrorState } from '../../components/ui';
import type { Language, Meta, ProblemDetail, Submission } from '../../types';
import { askAssistant, getInteraction, listInteractions, whyFixFailed } from './api';
import type { AssistantInteraction, AssistantRequest } from './types';
import './assistant.css';

// Props are a fixed contract used by Workspace, AssessmentRunner and IncidentWorkspace.
export interface AssistantPanelProps {
  problem: ProblemDetail; language: Language; code: string; latestSubmission?: Submission;
  assessmentSessionId?: string; incidentSessionId?: string;
}

interface QuickAction { key: string; label: string; icon: typeof Bug; question?: string; why?: boolean }
const FULL_ACTIONS: QuickAction[] = [
  { key: 'why', label: 'Why did my fix fail?', icon: Bug, why: true },
  { key: 'error', label: 'Explain this error', icon: Microscope, question: 'Explain the error in my latest run.' },
  { key: 'diagnosis', label: 'Review my diagnosis', icon: Stethoscope, question: 'Review my diagnosis.' },
  { key: 'repro', label: 'Suggest a reproduction', icon: Repeat2, question: 'How can I reproduce this failure?' },
];
// A guided assessment policy allows conceptual help only (server-enforced).
const GUIDED_ACTIONS: QuickAction[] = [
  { key: 'problem', label: 'Explain the problem', icon: BookOpen, question: 'Explain the problem and its requirements.' },
  { key: 'concept', label: 'Explain the concept', icon: Lightbulb, question: 'Explain the concept behind this bug category.' },
  { key: 'docs', label: 'Find documentation', icon: FileSearch, question: 'Find official documentation for this problem.' },
];
const GENERATION_LABELS: Record<string, string> = {
  deterministic: 'Deterministic analysis', model: 'Model answer', 'model-fallback': 'Model unavailable: deterministic analysis',
};

function inline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(/(`[^`\n]+`|\[\d{1,2}\])/g).filter(Boolean).map((part, index) => {
    if (part.length > 2 && part.startsWith('`') && part.endsWith('`')) return <code key={`${keyPrefix}-${index}`}>{part.slice(1, -1)}</code>;
    if (/^\[\d{1,2}\]$/.test(part)) return <span key={`${keyPrefix}-${index}`} className="assistant-citation">{part}</span>;
    return part;
  });
}

function RichText({ text }: { text: string }) {
  const parts = text.split(/(```[\s\S]*?(?:```|$))/g).filter(part => part.trim());
  return <>{parts.map((part, index) => part.startsWith('```')
    ? <pre key={index} className="assistant-code"><code>{part.replace(/^```[^\n]*\n?/, '').replace(/```$/, '')}</code></pre>
    : part.split(/\n{2,}/).map((paragraph, inner) => <p key={`${index}-${inner}`}>{inline(paragraph, `${index}-${inner}`)}</p>))}</>;
}

function validationNotes(interaction: AssistantInteraction): string[] {
  const validation = interaction.metadata.validation;
  const notes = [...(interaction.metadata.limitations || [])];
  if (!validation) return notes;
  if (validation.blocked) notes.push('Some content was removed because it resembled hidden tests or the reference solution.');
  if ((validation.unverified_urls || 0) + (validation.invalid_citations || 0) > 0) notes.push('Unverified links or citations were removed.');
  if (validation.low_grounding) notes.push('This answer is only loosely tied to your code and results. Check it against your test output.');
  return notes;
}

function Answer({ interaction }: { interaction: AssistantInteraction }) {
  const generation = interaction.metadata.generation;
  const grounding = interaction.metadata.grounding_score;
  return <article className="assistant-answer" aria-live="polite">
    <header>
      <span className="assistant-intent">{interaction.intent_label}</span>
      {interaction.status === 'completed' && <span className="assistant-meta">{generation ? GENERATION_LABELS[generation] || generation : ''}{grounding != null && ` · grounded ${Math.round(grounding * 100)}%`}{interaction.latency_ms != null && ` · ${ms(interaction.latency_ms)}`}</span>}
    </header>
    {interaction.question && <p className="assistant-question">“{interaction.question}”</p>}
    {pending(interaction.status) ? <div className="assistant-pending" role="status"><span className="evaluation-dots"><i /><i /><i /></span>Reading your code, results and the documentation…</div>
      : interaction.status === 'error' ? <p className="inline-error">{interaction.error || 'The assistant could not answer. Manual debugging is unaffected.'}</p>
        : <>
          {interaction.response?.sections.map(section => <section key={section.key} className="assistant-section"><h4>{section.title}</h4><RichText text={section.body} /></section>)}
          {validationNotes(interaction).length > 0 && <ul className="assistant-notes">{validationNotes(interaction).map(note => <li key={note}><Info size={12} />{note}</li>)}</ul>}
          {interaction.sources.length > 0 && <div className="assistant-sources"><h4>Sources</h4><ol>{interaction.sources.map((source, index) => <li key={`${source.url}-${index}`}><a href={source.url} target="_blank" rel="noreferrer"><span>[{index + 1}]</span>{source.title}<ExternalLink size={11} /></a></li>)}</ol></div>}
        </>}
  </article>;
}

export default function AssistantPanel({ problem, language, code, latestSubmission, assessmentSessionId, incidentSessionId }: AssistantPanelProps) {
  const client = useQueryClient();
  const [question, setQuestion] = useState('');
  const [activeId, setActiveId] = useState<string | null>(null);
  const meta = useQuery({ queryKey: ['meta'], queryFn: () => api<Meta>('/meta') });
  const assistance = problem.assistance;
  const inAssessment = assistance?.source === 'assessment';
  const disabled = inAssessment && assistance.ai === 'disabled';
  const guided = inAssessment && assistance.ai === 'guided';
  const history = useQuery({ queryKey: ['ai-interactions', problem.slug], queryFn: () => listInteractions(problem.slug), enabled: !disabled });
  const current = useQuery({ queryKey: ['ai-interaction', activeId], queryFn: () => getInteraction(activeId!), enabled: !!activeId,
    refetchInterval: query => query.state.error ? false : !query.state.data || pending(query.state.data.status) ? 1000 : false });
  const shown = current.data ?? history.data?.items[0];
  const completedId = current.data && !pending(current.data.status) ? current.data.id : null;
  // Refresh the history list once an answer arrives.
  useEffect(() => {
    if (completedId) void client.invalidateQueries({ queryKey: ['ai-interactions', problem.slug] });
  }, [completedId, client, problem.slug]);
  const request = (): AssistantRequest => ({
    language, code,
    // Point at the latest run only once it is evaluated; otherwise the server uses the latest evaluated run.
    ...(latestSubmission && latestSubmission.problem_id === problem.id && !pending(latestSubmission.status) ? { submission_id: latestSubmission.id } : {}),
    ...(assessmentSessionId ? { assessment_session_id: assessmentSessionId } : {}),
    ...(incidentSessionId ? { incident_session_id: incidentSessionId } : {}),
  });
  const ask = useMutation({
    mutationFn: (action: QuickAction | { question: string }) => 'why' in action && action.why
      ? whyFixFailed(problem.slug, request())
      : askAssistant(problem.slug, { ...request(), question: ('question' in action && action.question) || question.trim() }),
    onSuccess: row => { client.setQueryData(['ai-interaction', row.id], row); setActiveId(row.id); setQuestion(''); },
    onError: error => toast.error(error.message),
  });
  const busy = ask.isPending || (!!current.data && pending(current.data.status));
  function submit(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) ask.mutate({ question: question.trim() });
  }
  if (disabled) return <div className="assistant-panel"><div className="assistant-policy"><ShieldAlert size={16} /><div><strong>AI assistance is disabled for this assessment.</strong><span>Your work is evaluated independently. Use the public tests and your own reasoning.</span></div></div></div>;
  const actions = guided ? GUIDED_ACTIONS : FULL_ACTIONS;
  return <div className="assistant-panel">
    <div className="assistant-head"><span className="eyebrow"><Bot size={13} />DEBUGGING ASSISTANT</span><span className="assistant-mode">{meta.data?.ai_enabled ? meta.data.ai_model : 'Deterministic analysis'}</span></div>
    <p className="assistant-intro">{meta.data && !meta.data.ai_enabled
      ? 'No model is configured, so answers are built from your code, your test results and official documentation.'
      : 'Answers use your current code, your latest results and official documentation. Hidden tests and reference solutions are never shared.'}</p>
    {guided && <div className="assistant-policy"><ShieldAlert size={16} /><div><strong>Conceptual guidance only</strong><span>This assessment allows explanations of the problem, concepts and documentation, not patch reviews.</span></div></div>}
    <div className="assistant-actions">{actions.map(action => { const Icon = action.icon; return <button key={action.key} className="button secondary small" disabled={busy} onClick={() => ask.mutate(action)}><Icon size={13} />{action.label}</button>; })}</div>
    <form className="assistant-ask" onSubmit={submit}>
      <label htmlFor="assistant-question" className="sr-only">Ask the debugging assistant</label>
      <textarea id="assistant-question" value={question} maxLength={2000} disabled={busy} onChange={event => setQuestion(event.target.value)}
        onKeyDown={event => { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) submit(event); }}
        placeholder="Ask about your failure, an error, a concept, or your diagnosis…" />
      <div><span>{question.length} / 2000</span><button className="button primary small" type="submit" disabled={busy || !question.trim()}>{busy ? <LoaderCircle size={13} className="spin" /> : <Send size={13} />}Ask</button></div>
    </form>
    {current.isError ? <ErrorState error={current.error} retry={() => void current.refetch()} /> : shown && <Answer interaction={shown} />}
    {history.isError ? <ErrorState error={history.error} /> : history.data && history.data.items.length > 1 && <div className="assistant-history"><h4><Clock3 size={13} />Earlier questions</h4>{history.data.items.filter(row => row.id !== shown?.id).slice(0, 6).map(row => <button key={row.id} className="assistant-history-row" onClick={() => { client.setQueryData(['ai-interaction', row.id], row); setActiveId(row.id); }}><span>{row.intent_label}</span><small>{row.question || '—'}</small></button>)}</div>}
  </div>;
}
