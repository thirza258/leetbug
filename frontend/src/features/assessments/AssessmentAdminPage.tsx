import { Archive, ArrowRight, Copy, LoaderCircle, MailPlus, Pencil, Plus, Rocket, ShieldCheck, Trash2, Users, X } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import { languageNames } from '../../lib/constants';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import Modal from '../../components/Modal';
import type { Language } from '../../types';
import {
  adminAssessments, adminInvitations, adminSessions, archiveAssessment, correctSession, createAssessment, createInvitations,
  publishAssessment, releaseSession, revokeInvitation, updateAssessment,
} from './api';
import { dimensionNames, score, sessionNames, typeNames, when } from './format';
import type { AdminAssessment, AdminSession, AiPolicy, AssessmentType, CreatedInvitation, Dimension, HintPolicy } from './types';
import './assessments.css';

const dimensions = Object.keys(dimensionNames) as Dimension[];
const defaultWeights: Record<Dimension, number> = { diagnosis: 25, correctness: 30, verification: 15, quality: 10, explanation: 10, time: 10 };

export default function AssessmentAdminPage() {
  const { user } = useAuth();
  const [editing, setEditing] = useState<AdminAssessment | 'new' | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: ['admin-assessments'], queryFn: adminAssessments, enabled: !!user?.is_admin });
  if (!user?.is_admin) return <div className="page"><EmptyState icon={<ShieldCheck size={28} />} title="Admin access required"><p>Assessment administration is restricted to administrators.</p><Link className="button primary" to="/assessments">Back to assessments</Link></EmptyState></div>;
  const current = list.data?.items.find(item => item.id === selected) ?? null;
  return <div className="page">
    <PageHeading eyebrow="ADMIN" title="Assessment administration" description="Configure, validate and publish assessments; invite candidates; review sessions and apply audited corrections." action={<button className="button primary" onClick={() => setEditing('new')}><Plus size={15} />New assessment</button>} />
    {list.isPending ? <Loading /> : list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} /> : <div className="problem-table-wrap"><table className="data-table"><thead><tr><th>ASSESSMENT</th><th>TYPE</th><th>STATUS</th><th>VISIBILITY</th><th>SESSIONS</th><th aria-label="Actions" /></tr></thead><tbody>
      {list.data.items.map(item => <tr key={item.id} className={item.id === selected ? 'asm-selected-row' : undefined}><td><strong>{item.title}</strong><div className="muted">{item.slug} · v{item.version}{item.validation_errors.length ? ` · ${item.validation_errors.length} issue(s)` : ''}</div></td>
        <td>{typeNames[item.assessment_type]}</td><td><span className={`asm-status ${item.status}`}>{item.status}</span></td><td>{item.visibility}</td>
        <td>{Object.values(item.session_counts).reduce((sum, count) => sum + count, 0)}</td>
        <td><div className="row-actions"><button className="button secondary small" onClick={() => setEditing(item)} disabled={item.status === 'archived'}><Pencil size={13} />Edit</button><button className="button secondary small" onClick={() => setSelected(item.id === selected ? null : item.id)}><Users size={13} />Manage</button></div></td></tr>)}
    </tbody></table></div>}
    {current && <AssessmentManager key={current.id} assessment={current} />}
    {editing && <Modal label="Assessment editor" onDismiss={() => setEditing(null)}><AssessmentForm initial={editing === 'new' ? null : editing} onDone={() => setEditing(null)} /></Modal>}
  </div>;
}

function toLocal(value: string | null) {
  if (!value) return '';
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function AssessmentForm({ initial, onDone }: { initial: AdminAssessment | null; onDone: () => void }) {
  const client = useQueryClient();
  const configuration = initial?.configuration;
  const [languages, setLanguages] = useState<Language[]>(configuration?.languages ?? []);
  const [weights, setWeights] = useState<Record<Dimension, number>>({ ...defaultWeights, ...(initial?.scoring_rubric.weights ?? {}) });
  const save = useMutation({ mutationFn: (body: Record<string, unknown>) => initial ? updateAssessment(initial.id, body) : createAssessment(body),
    onSuccess: () => { toast.success(initial ? 'Assessment updated.' : 'Draft assessment created.'); void client.invalidateQueries({ queryKey: ['admin-assessments'] }); onDone(); },
    onError: error => toast.error(error.message) });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? '').trim();
    const number = (name: string) => text(name) ? Number(text(name)) : null;
    const date = (name: string) => text(name) ? new Date(text(name)).toISOString() : null;
    const body: Record<string, unknown> = {
      title: text('title'), description: text('description'), assessment_type: text('assessment_type') as AssessmentType,
      duration_seconds: Math.round(Number(text('duration')) * 60), visibility: text('visibility'),
      configuration: { problems: text('problems').split(/[\s,]+/).filter(Boolean), languages,
        diagnosis_required: form.has('diagnosis_required'), explanation_required: form.has('explanation_required'),
        max_attempts: number('max_attempts'), max_sessions: number('max_sessions'), randomize_order: form.has('randomize_order'),
        feedback: text('feedback'), candidate_report: text('candidate_report'), require_quality_approved: form.has('require_quality_approved') },
      scoring_rubric: { weights }, assistance_policy: { ai: text('ai') as AiPolicy, hints: text('hints') as HintPolicy },
      available_from: date('available_from'), available_until: date('available_until'),
      competency_profile_id: text('competency_profile_id') || null,
    };
    if (!initial) {
      if (text('slug')) body.slug = text('slug');
      if (text('organization_id')) body.organization_id = text('organization_id');
    }
    save.mutate(body);
  }
  return <form className="asm-form" onSubmit={submit}>
    <div className="modal-heading"><span>{initial ? `Edit ${initial.title}` : 'New assessment'}</span><button type="button" className="icon-button" aria-label="Close editor" onClick={onDone}><X size={18} /></button></div>
    {initial?.status === 'published' && <p className="asm-modal-text">Saving a published assessment creates version {initial.version + 1}. Running sessions keep the version they started with.</p>}
    <label>Title<input name="title" required minLength={5} maxLength={150} defaultValue={initial?.title} /></label>
    {!initial && <label>Slug <small>Optional; generated from the title.</small><input name="slug" pattern="[a-z0-9][a-z0-9-]{2,99}" /></label>}
    <label>Description<textarea name="description" rows={3} maxLength={5000} defaultValue={initial?.description} /></label>
    <div className="asm-form-row">
      <label>Type<select name="assessment_type" defaultValue={initial?.assessment_type ?? 'individual'}>{(Object.keys(typeNames) as AssessmentType[]).map(value => <option key={value} value={value}>{typeNames[value]}</option>)}</select></label>
      <label>Duration (minutes)<input name="duration" type="number" min={5} max={240} required defaultValue={initial ? Math.round(initial.duration_seconds / 60) : 60} /></label>
      <label>Visibility<select name="visibility" defaultValue={initial?.visibility ?? 'public'}><option value="public">Public</option><option value="private">Private (members and invited)</option><option value="invitation">Invitation only</option></select></label>
    </div>
    <label>Challenges <small>Problem slugs, one per line, in order.</small><textarea name="problems" rows={4} required defaultValue={configuration?.problems.join('\n')} /></label>
    <fieldset className="asm-fieldset"><legend>Allowed languages <small>(none selected = any offered)</small></legend>{(Object.keys(languageNames) as Language[]).map(value => <label key={value} className="asm-check"><input type="checkbox" checked={languages.includes(value)} onChange={event => setLanguages(event.target.checked ? [...languages, value] : languages.filter(item => item !== value))} />{languageNames[value]}</label>)}</fieldset>
    <div className="asm-form-row">
      <label>AI assistance<select name="ai" defaultValue={initial?.assistance_policy.ai ?? 'disabled'}><option value="disabled">Disabled</option><option value="guided">Guided (conceptual only)</option><option value="enabled">Enabled and recorded</option></select></label>
      <label>Hints<select name="hints" defaultValue={initial?.assistance_policy.hints ?? 'disabled'}><option value="disabled">Disabled</option><option value="restricted">First hint only</option><option value="enabled">Enabled and recorded</option></select></label>
      <label>Feedback<select name="feedback" defaultValue={configuration?.feedback ?? 'immediate'}><option value="immediate">Immediate</option><option value="delayed">After review</option></select></label>
      <label>Candidate report<select name="candidate_report" defaultValue={configuration?.candidate_report ?? 'full'}><option value="full">Full</option><option value="summary">Summary</option></select></label>
    </div>
    <div className="asm-form-row">
      <label>Submissions per challenge<input name="max_attempts" type="number" min={1} max={50} defaultValue={configuration?.max_attempts ?? ''} placeholder="Unlimited" /></label>
      <label>Sessions per candidate<input name="max_sessions" type="number" min={1} max={50} defaultValue={configuration?.max_sessions ?? ''} placeholder="Type default" /></label>
      <label>Opens<input name="available_from" type="datetime-local" defaultValue={toLocal(initial?.available_from ?? null)} /></label>
      <label>Closes<input name="available_until" type="datetime-local" defaultValue={toLocal(initial?.available_until ?? null)} /></label>
    </div>
    <fieldset className="asm-fieldset"><legend>Rules</legend>
      <label className="asm-check"><input type="checkbox" name="diagnosis_required" defaultChecked={configuration?.diagnosis_required ?? true} />Diagnosis required before submitting</label>
      <label className="asm-check"><input type="checkbox" name="explanation_required" defaultChecked={configuration?.explanation_required ?? false} />Fix explanation required</label>
      <label className="asm-check"><input type="checkbox" name="randomize_order" defaultChecked={configuration?.randomize_order ?? false} />Randomize challenge order per session</label>
      <label className="asm-check"><input type="checkbox" name="require_quality_approved" defaultChecked={configuration?.require_quality_approved ?? false} />Require problems to pass the quality gate</label>
    </fieldset>
    <fieldset className="asm-fieldset"><legend>Scoring weights</legend><div className="asm-weights">{dimensions.map(name => <label key={name}>{dimensionNames[name]}<input type="number" min={0} max={100} value={weights[name]} onChange={event => setWeights({ ...weights, [name]: Number(event.target.value) })} /></label>)}</div></fieldset>
    <div className="asm-form-row">
      {!initial && <label>Organization ID <small>Optional</small><input name="organization_id" maxLength={36} /></label>}
      <label>Competency profile ID <small>Optional</small><input name="competency_profile_id" maxLength={36} defaultValue={initial?.competency_profile_id ?? ''} /></label>
    </div>
    <div className="asm-modal-actions"><button type="button" className="button secondary" onClick={onDone}>Cancel</button><button className="button primary" disabled={save.isPending}>{save.isPending && <LoaderCircle size={14} className="spin" />}{initial ? 'Save changes' : 'Create draft'}</button></div>
  </form>;
}

function AssessmentManager({ assessment }: { assessment: AdminAssessment }) {
  const client = useQueryClient();
  const [emails, setEmails] = useState('');
  const [created, setCreated] = useState<CreatedInvitation[]>([]);
  const [correcting, setCorrecting] = useState<AdminSession | null>(null);
  const sessions = useQuery({ queryKey: ['admin-assessment-sessions', assessment.id], queryFn: () => adminSessions(assessment.id) });
  const invitations = useQuery({ queryKey: ['admin-assessment-invitations', assessment.id], queryFn: () => adminInvitations(assessment.id) });
  const refresh = () => { void client.invalidateQueries({ queryKey: ['admin-assessments'] }); void client.invalidateQueries({ queryKey: ['admin-assessment-sessions', assessment.id] }); void client.invalidateQueries({ queryKey: ['admin-assessment-invitations', assessment.id] }); };
  const action = useMutation({ mutationFn: (kind: 'publish' | 'archive') => kind === 'publish' ? publishAssessment(assessment.id) : archiveAssessment(assessment.id),
    onSuccess: (_, kind) => { toast.success(kind === 'publish' ? 'Assessment published.' : 'Assessment archived.'); refresh(); }, onError: error => toast.error(error.message) });
  const invite = useMutation({ mutationFn: () => createInvitations(assessment.id, emails.split(/[\s,;]+/).filter(Boolean), 14),
    onSuccess: result => { setCreated(result.items); setEmails(''); refresh(); }, onError: error => toast.error(error.message) });
  const release = useMutation({ mutationFn: releaseSession, onSuccess: () => { toast.success('Report released to the candidate.'); refresh(); }, onError: error => toast.error(error.message) });
  async function revoke(id: string) {
    try { await revokeInvitation(id); refresh(); } catch (error) { toast.error((error as Error).message); }
  }
  function copy(text: string) { navigator.clipboard.writeText(text).then(() => toast.success('Link copied.')).catch(() => toast.error('Clipboard is unavailable.')); }
  return <section className="surface asm-manager" aria-label={`Manage ${assessment.title}`}>
    <div className="surface-heading"><h2>{assessment.title}</h2><div className="row-actions">
      {assessment.status !== 'published' && assessment.status !== 'archived' && <button className="button primary small" disabled={action.isPending} onClick={() => action.mutate('publish')}><Rocket size={13} />Publish</button>}
      {assessment.status !== 'archived' && <button className="button secondary small" disabled={action.isPending} onClick={() => action.mutate('archive')}><Archive size={13} />Archive</button>}
      <Link className="text-link" to={`/assessments/${assessment.slug}`}>Candidate view <ArrowRight size={13} /></Link></div></div>
    {assessment.validation_errors.length > 0 && <ul className="inline-error asm-errors">{assessment.validation_errors.map(error => <li key={error}>{error}</li>)}</ul>}
    <h3 className="asm-subheading">Invitations</h3>
    <div className="asm-invite"><textarea aria-label="Candidate emails" rows={2} placeholder="candidate@example.com, another@example.com" value={emails} onChange={event => setEmails(event.target.value)} /><button className="button secondary small" disabled={!emails.trim() || invite.isPending || assessment.status === 'archived'} onClick={() => invite.mutate()}><MailPlus size={13} />Create invitations</button></div>
    {created.length > 0 && <div className="success-note asm-created"><div><strong>Copy these links now — they are shown once.</strong>{created.map(row => <div key={row.id} className="asm-link-row"><span>{row.email}</span><code>{window.location.origin}{row.path}</code><button className="icon-button" aria-label={`Copy link for ${row.email}`} onClick={() => copy(`${window.location.origin}${row.path}`)}><Copy size={13} /></button></div>)}</div></div>}
    {invitations.data && invitations.data.items.length > 0 && <div className="history-table-wrap"><table className="data-table"><thead><tr><th>EMAIL</th><th>STATUS</th><th>EXPIRES</th><th aria-label="Actions" /></tr></thead><tbody>{invitations.data.items.map(row => <tr key={row.id}><td>{row.email}</td><td>{row.status}</td><td>{when(row.expires_at)}</td><td>{row.status === 'pending' && <button className="icon-button" aria-label={`Revoke invitation for ${row.email}`} onClick={() => void revoke(row.id)}><Trash2 size={14} /></button>}</td></tr>)}</tbody></table></div>}
    <h3 className="asm-subheading">Sessions</h3>
    {sessions.isPending ? <Loading /> : sessions.isError ? <ErrorState error={sessions.error} /> : !sessions.data.items.length ? <p className="muted">No candidate has started this assessment yet.</p>
      : <div className="history-table-wrap"><table className="data-table"><thead><tr><th>CANDIDATE</th><th>STATUS</th><th>STARTED</th><th>SCORE</th><th>VERSION</th><th aria-label="Actions" /></tr></thead><tbody>
        {sessions.data.items.map(row => <tr key={row.id}><td><strong>@{row.candidate.username}</strong><div className="muted">{row.candidate.email}</div></td><td><span className={`asm-status ${row.status}`}>{sessionNames[row.status]}</span></td><td>{when(row.started_at)}</td><td>{score(row.total_score)}{row.report_version > 1 ? ` (v${row.report_version})` : ''}</td><td>v{row.assessment_version}</td>
          <td><div className="row-actions">{row.finalized_at && <Link className="button secondary small" to={`/assessment-sessions/${row.id}/report`}>Report</Link>}{row.finalized_at && !row.released && <button className="button secondary small" disabled={release.isPending} onClick={() => release.mutate(row.id)}>Release</button>}{row.finalized_at && <button className="button secondary small" onClick={() => setCorrecting(row)}>Correct</button>}</div></td></tr>)}
      </tbody></table></div>}
    {correcting && <Modal label="Correct assessment result" onDismiss={() => setCorrecting(null)}><CorrectionForm session={correcting} problems={assessment.configuration.problems} onDone={() => { setCorrecting(null); refresh(); }} /></Modal>}
  </section>;
}

function CorrectionForm({ session, problems, onDone }: { session: AdminSession; problems: string[]; onDone: () => void }) {
  const correct = useMutation({ mutationFn: (body: Record<string, unknown>) => correctSession(session.id, body),
    onSuccess: result => { toast.success(`Correction saved as report version ${result.report_version}.`); onDone(); }, onError: error => toast.error(error.message) });
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const text = (name: string) => String(form.get(name) ?? '').trim();
    const body: Record<string, unknown> = { reason: text('reason') };
    if (text('total_score')) body.total_score = Number(text('total_score'));
    if (text('challenge') && text('dimension') && text('value')) body.challenge_scores = { [text('challenge')]: { [text('dimension')]: Number(text('value')) } };
    correct.mutate(body);
  }
  return <form className="asm-form" onSubmit={submit}>
    <div className="modal-heading"><span>Correct @{session.candidate.username}'s result</span><button type="button" className="icon-button" aria-label="Close" onClick={onDone}><X size={18} /></button></div>
    <p className="asm-modal-text">Corrections are audited, versioned, and listed in the candidate's report. Current score: {score(session.total_score)}.</p>
    <label>Reason<textarea name="reason" rows={3} required minLength={10} maxLength={2000} /></label>
    <div className="asm-form-row"><label>Challenge<select name="challenge" defaultValue=""><option value="">No challenge change</option>{problems.map(slug => <option key={slug} value={slug}>{slug}</option>)}</select></label>
      <label>Dimension<select name="dimension" defaultValue="diagnosis">{dimensions.map(name => <option key={name} value={name}>{dimensionNames[name]}</option>)}</select></label>
      <label>New value<input name="value" type="number" min={0} max={100} /></label></div>
    <label>Override total score <small>Optional; applied after challenge changes.</small><input name="total_score" type="number" min={0} max={100} step="0.01" /></label>
    <div className="asm-modal-actions"><button type="button" className="button secondary" onClick={onDone}>Cancel</button><button className="button primary" disabled={correct.isPending}>Save correction</button></div>
  </form>;
}
