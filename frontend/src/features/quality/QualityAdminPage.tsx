import { CheckCircle2, ChevronLeft, ChevronRight, CircleAlert, CircleDashed, FlaskConical, LockKeyhole, Play, RotateCcw, Search, ShieldCheck, Upload, X, XCircle } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import { dateLabel, languageNames } from '../../lib/constants';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import type { Language } from '../../types';
import { activeRun, label, qualityApi } from './api';
import type { GateConfig, MutationCase, MutationRun, OverviewRow, PipelineStep, Thresholds } from './types';
import './quality.css';

type Tab = 'problems' | 'community' | 'gates';

export default function QualityAdminPage() {
  const { user, loading } = useAuth();
  const [tab, setTab] = useState<Tab>('problems');
  if (loading) return <Loading />;
  if (!user?.is_admin) return <div className="page"><EmptyState title="Admin access required"><p>This page is restricted to administrators.</p><Link className="button primary" to="/">Back to library</Link></EmptyState></div>;
  return <div className="page qa-page">
    <PageHeading eyebrow="ADMIN" title="Problem quality" description="Validate challenges with mutation testing, review surviving mutants, tune quality gates, and publish drafts that pass." />
    <div className="tab-links qa-tabs" role="tablist">
      {([['problems', 'Problems'], ['community', 'Community drafts'], ['gates', 'Quality gates']] as [Tab, string][]).map(([key, text]) =>
        <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{text}</button>)}
    </div>
    {tab === 'problems' ? <ProblemsTab /> : tab === 'community' ? <CommunityTab /> : <GatesTab />}
  </div>;
}

export function QualityBadge({ status, stale }: { status: string | null | undefined; stale?: boolean }) {
  const value = stale ? 'stale' : status || 'unvalidated';
  const Icon = value === 'approved' ? CheckCircle2 : value === 'requires_revision' ? XCircle : value === 'stale' ? CircleAlert : CircleDashed;
  return <span className={`qa-badge ${value}`}><Icon size={12} />{value === 'requires_revision' ? 'Needs revision' : label(value)}</span>;
}

function ProblemsTab() {
  const [filters, setFilters] = useState({ q: '', category: '', gate: '', visibility: '', page: 1 });
  const [selected, setSelected] = useState<string | null>(null);
  const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value !== '' && value !== 1).map(([key, value]) => [key, String(value)]));
  const overview = useQuery({ queryKey: ['quality-overview', params.toString()], queryFn: () => qualityApi.overview(params),
    refetchInterval: query => query.state.data?.items.some(row => activeRun(row.latest_run?.status)) ? 3000 : false });
  const set = (key: string, value: string) => setFilters(current => ({ ...current, [key]: value, page: 1 }));
  return <>
    {overview.data && <div className="qa-summary">
      <Stat label="Approved" value={overview.data.summary.approved} tone="green" />
      <Stat label="Need revision" value={overview.data.summary.requires_revision} tone="coral" />
      <Stat label="Unvalidated" value={overview.data.summary.unvalidated} />
      <Stat label="Published community problems approved" value={overview.data.summary.published_new_approved_rate == null ? '—' : `${overview.data.summary.published_new_approved_rate}%`} detail={`${overview.data.summary.published_new} published`} />
    </div>}
    <div className="qa-filters">
      <label className="search-input"><Search size={16} /><input aria-label="Search problems" placeholder="Search by title or slug…" value={filters.q} onChange={event => set('q', event.target.value)} /></label>
      <select aria-label="Category" value={filters.category} onChange={event => set('category', event.target.value)}><option value="">All categories</option>{overview.data?.categories.map(category => <option key={category} value={category}>{label(category)}</option>)}</select>
      <select aria-label="Gate status" value={filters.gate} onChange={event => set('gate', event.target.value)}><option value="">Any gate status</option><option value="approved">Approved</option><option value="requires_revision">Needs revision</option><option value="unvalidated">Unvalidated</option><option value="stale">Stale</option></select>
      <select aria-label="Visibility" value={filters.visibility} onChange={event => set('visibility', event.target.value)}><option value="">Any visibility</option><option value="public">Public</option><option value="draft">Draft</option><option value="incident">Incident</option><option value="assessment">Assessment</option></select>
    </div>
    {overview.isPending ? <Loading label="Loading quality overview…" /> : overview.isError ? <ErrorState error={overview.error} retry={() => void overview.refetch()} /> : !overview.data.items.length ? <EmptyState icon={<FlaskConical size={28} />} title="No problems match"><p>Change the filters to see more problems.</p></EmptyState> : <>
      <div className="qa-table-wrap"><table className="qa-table">
        <thead><tr><th>ID</th><th>PROBLEM</th><th>VERSION</th><th>SCORE</th><th>GATE</th><th>LAST RUN</th><th aria-label="Actions" /></tr></thead>
        <tbody>{overview.data.items.map(row => <ProblemRow key={row.id} row={row} open={selected === row.slug} onOpen={() => setSelected(selected === row.slug ? null : row.slug)} />)}</tbody>
      </table></div>
      <div className="catalog-footer"><span>{overview.data.total} problems</span><div className="pagination">
        <button className="icon-button" aria-label="Previous page" disabled={filters.page <= 1} onClick={() => setFilters(current => ({ ...current, page: current.page - 1 }))}><ChevronLeft size={16} /></button><span>{filters.page}</span>
        <button className="icon-button" aria-label="Next page" disabled={filters.page * overview.data.limit >= overview.data.total} onClick={() => setFilters(current => ({ ...current, page: current.page + 1 }))}><ChevronRight size={16} /></button>
      </div></div>
    </>}
    {selected && <ProblemQuality key={selected} slug={selected} onClose={() => setSelected(null)} />}
  </>;
}

function Stat({ label: text, value, detail, tone = '' }: { label: string; value: number | string; detail?: string; tone?: string }) {
  return <div className={`qa-stat ${tone}`}><span>{text}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>;
}

function ProblemRow({ row, open, onOpen }: { row: OverviewRow; open: boolean; onOpen: () => void }) {
  return <tr className={open ? 'selected' : ''}>
    <td className="mono">{row.id}</td>
    <td><strong className="qa-title">{row.title}</strong><span className="qa-sub">{row.slug} · {label(row.category)} · {row.visibility}{row.source === 'community' ? ' · community' : ''}</span></td>
    <td className="mono">v{row.version}</td>
    <td className="mono">{row.latest_run?.mutation_score == null ? '—' : `${row.latest_run.mutation_score}%`}</td>
    <td>{activeRun(row.latest_run?.status) ? <span className="qa-badge running"><CircleDashed size={12} className="spin" />{row.latest_run?.status}</span> : <QualityBadge status={row.quality_status} stale={row.stale} />}</td>
    <td className="qa-sub">{row.latest_run ? `${dateLabel(row.latest_run.created_at)} · ${languageNames[row.latest_run.language as Language] ?? row.latest_run.language}` : 'Never'}</td>
    <td><button className="button secondary small" onClick={onOpen} aria-expanded={open}>{open ? 'Close' : 'Inspect'}</button></td>
  </tr>;
}

function ProblemQuality({ slug, onClose }: { slug: string; onClose: () => void }) {
  const client = useQueryClient();
  const runs = useQuery({ queryKey: ['quality-runs', slug], queryFn: () => qualityApi.runs(slug),
    refetchInterval: query => query.state.data?.items.some(run => activeRun(run.status)) ? 2000 : false });
  const history = useQuery({ queryKey: ['quality-history', slug], queryFn: () => qualityApi.history(slug) });
  const [runId, setRunId] = useState<string | null>(null);
  const current = runId ?? runs.data?.items[0]?.id ?? null;
  const publish = useMutation({ mutationFn: (action: 'publish' | 'unpublish') => action === 'publish' ? qualityApi.publish(slug) : qualityApi.unpublish(slug),
    onSuccess: (_, action) => { toast.success(action === 'publish' ? 'Problem published.' : 'Problem moved back to draft.'); void client.invalidateQueries({ queryKey: ['quality-overview'] }); void client.invalidateQueries({ queryKey: ['quality-runs', slug] }); },
    onError: error => toast.error(error.message) });
  if (runs.isPending) return <section className="surface qa-panel"><Loading label="Loading quality runs…" /></section>;
  if (runs.isError) return <section className="surface qa-panel"><ErrorState error={runs.error} retry={() => void runs.refetch()} /></section>;
  const problem = runs.data.problem;
  return <section className="surface qa-panel" aria-label={`Quality for ${problem.title}`}>
    <div className="qa-panel-heading"><div><span className="eyebrow">QUALITY REPORT</span><h2>{problem.title}</h2><span className="qa-sub">v{problem.version} · {problem.visibility} · <QualityBadge status={problem.quality_status} /></span></div>
      <div className="qa-actions">{problem.visibility === 'draft' && <button className="button primary small" disabled={publish.isPending} onClick={() => publish.mutate('publish')}><Upload size={13} />Publish</button>}{problem.visibility === 'public' && problem.source === 'community' && <button className="button secondary small" disabled={publish.isPending} onClick={() => publish.mutate('unpublish')}>Unpublish</button>}<button className="icon-button" aria-label="Close quality report" onClick={onClose}><X size={17} /></button></div></div>
    <StartRun slug={slug} languages={problem.languages} onStarted={id => { setRunId(id); void client.invalidateQueries({ queryKey: ['quality-runs', slug] }); void client.invalidateQueries({ queryKey: ['quality-overview'] }); }} />
    {runs.data.items.length > 0 && <div className="qa-run-list" role="list">{runs.data.items.map(run => <button role="listitem" key={run.id} className={`qa-run-chip ${run.id === current ? 'active' : ''}`} onClick={() => setRunId(run.id)}><span className="mono">v{run.problem_version} · {run.language}</span>{activeRun(run.status) ? <span className="qa-badge running">{run.status}</span> : run.status === 'failed' ? <span className="qa-badge requires_revision">failed</span> : <QualityBadge status={run.gate_status} />}<small>{run.mutation_score == null ? '—' : `${run.mutation_score}%`} · {dateLabel(run.created_at)}</small></button>)}</div>}
    {history.data && history.data.versions.length > 1 && <p className="qa-sub qa-history">Version history: {history.data.versions.map(version => `v${version.version} ${version.runs.map(run => `${run.language} ${run.mutation_score ?? '—'}% ${run.gate_status === 'approved' ? '✓' : '✗'}`).join(', ')}`).join(' · ')}</p>}
    {current ? <RunDetail key={current} runId={current} /> : <p className="muted">No quality runs yet. Start one above.</p>}
  </section>;
}

function StartRun({ slug, languages, onStarted }: { slug: string; languages: string[]; onStarted: (id: string) => void }) {
  const [language, setLanguage] = useState(languages[0] ?? 'python');
  const [maxMutants, setMaxMutants] = useState(24);
  const [selected, setSelected] = useState<string[]>([]);
  const operators = useQuery({ queryKey: ['quality-operators'], queryFn: qualityApi.operators, staleTime: Infinity });
  const start = useMutation({ mutationFn: () => qualityApi.startRun(slug, { language, max_mutants: maxMutants, ...(selected.length ? { operators: selected } : {}) }),
    onSuccess: run => { toast.success('Quality validation queued.'); onStarted(run.id); }, onError: error => toast.error(error.message) });
  function submit(event: FormEvent) { event.preventDefault(); start.mutate(); }
  return <form className="qa-start" onSubmit={submit}>
    <label>Language<select value={language} onChange={event => setLanguage(event.target.value)}>{languages.map(value => <option key={value} value={value}>{languageNames[value as Language] ?? value}</option>)}</select></label>
    <label>Max mutants<input type="number" min={1} max={60} value={maxMutants} onChange={event => setMaxMutants(Math.max(1, Math.min(60, Number(event.target.value) || 1)))} /></label>
    <details className="qa-operators"><summary>Operators ({selected.length ? selected.length : 'all'})</summary><div>{operators.data?.operators.map(operator => <label key={operator.id} className="qa-check"><input type="checkbox" checked={selected.includes(operator.id)} onChange={event => setSelected(current => event.target.checked ? [...current, operator.id] : current.filter(item => item !== operator.id))} />{operator.label}</label>)}</div></details>
    <button className="button primary small" disabled={start.isPending}><Play size={13} />Run validation</button>
  </form>;
}

const stepIcon = (status: PipelineStep['status']) => status === 'passed' ? <CheckCircle2 size={14} className="green" /> : status === 'failed' ? <XCircle size={14} className="coral" /> : status === 'warning' ? <CircleAlert size={14} className="amber" /> : <CircleDashed size={14} className="muted" />;

function RunDetail({ runId }: { runId: string }) {
  const run = useQuery({ queryKey: ['quality-run', runId], queryFn: () => qualityApi.run(runId),
    refetchInterval: query => activeRun(query.state.data?.status) ? 2000 : false });
  if (run.isPending) return <Loading label="Loading run…" />;
  if (run.isError) return <ErrorState error={run.error} retry={() => void run.refetch()} />;
  const data: MutationRun = run.data;
  const report = data.report ?? {};
  const summary = report.mutation;
  const steps = data.pipeline ?? [];
  return <div className="qa-run">
    {data.error && <p className="inline-error">{data.error}</p>}
    {activeRun(data.status) && <p className="qa-sub" role="status"><CircleDashed size={13} className="spin" /> {label(data.status)} — {data.total_mutations ? `${data.total_mutations} mutants` : 'validating the starter and reference'}…</p>}
    <div className="qa-grid">
      <div><h3>Pipeline</h3><ol className="qa-steps">{steps.map(step => <li key={step.step}>{stepIcon(step.status)}<div><strong>{label(step.step)}</strong><span>{step.detail}</span></div></li>)}</ol></div>
      <div><h3>Quality gate</h3>{report.gate ? <ul className="qa-checks">{report.gate.checks.map(check => <li key={check.name} className={check.passed ? 'passed' : 'failed'}>{check.passed ? <CheckCircle2 size={14} /> : <XCircle size={14} />}<div><strong>{label(check.name)}</strong><span>{check.detail}</span></div></li>)}</ul> : <p className="muted">Available when the run completes.</p>}</div>
    </div>
    {summary && <div className="qa-summary compact">
      <Stat label="Mutation score" value={summary.score == null ? '—' : `${summary.score}%`} detail={`${summary.detected} / ${summary.scored} scorable`} tone={summary.score != null && summary.score >= 80 ? 'green' : 'coral'} />
      <Stat label="Killed" value={summary.killed} detail={`${summary.timed_out} by timeout`} />
      <Stat label="Survived" value={summary.survived} tone={summary.survived ? 'coral' : ''} />
      <Stat label="Critical killed" value={`${summary.critical_killed}/${summary.critical_scored}`} tone={summary.critical_survived ? 'coral' : 'green'} />
      <Stat label="Excluded" value={summary.invalid + summary.equivalent + summary.errors} detail={`${summary.invalid} invalid · ${summary.equivalent} equivalent · ${summary.errors} errors`} />
    </div>}
    {report.tests && <p className="qa-sub qa-inventory">{report.tests.public} public · {report.tests.hidden} hidden tests · {report.tests.with_state_assertions} with state assertions · edge-case indicators {report.tests.edge_case_coverage.count}/{report.tests.edge_case_coverage.total}{report.tests.concurrency_probes != null ? ` · ${report.tests.concurrency_probes} concurrency probes` : ''}{report.tests.meaningful_hidden_tests.length ? ` · meaningful hidden: ${report.tests.meaningful_hidden_tests.join(', ')}` : ''}</p>}
    {report.leakage && report.leakage.findings.length > 0 && <ul className="qa-findings">{report.leakage.findings.map((finding, index) => <li key={index} className={finding.severity}><strong>{label(finding.kind)}</strong> in {finding.source}: <code>{finding.excerpt}</code></li>)}</ul>}
    {data.total_mutations > 0 && <Mutants runId={runId} active={activeRun(data.status)} />}
  </div>;
}

const caseFilters = ['', 'survived', 'critical', 'killed', 'timeout', 'invalid', 'equivalent', 'error'];

function Mutants({ runId, active }: { runId: string; active: boolean }) {
  const [filter, setFilter] = useState('survived');
  const cases = useQuery({ queryKey: ['quality-cases', runId, filter], queryFn: () => qualityApi.cases(runId, filter), refetchInterval: active ? 2500 : false });
  return <div className="qa-mutants">
    <div className="qa-mutants-heading"><h3>Mutants</h3><div className="qa-filter-chips" role="group" aria-label="Mutant filter">{caseFilters.map(value => <button key={value || 'all'} className={filter === value ? 'active' : ''} onClick={() => setFilter(value)}>{value ? label(value) : 'all'}</button>)}</div></div>
    {cases.isPending ? <Loading label="Loading mutants…" /> : cases.isError ? <ErrorState error={cases.error} /> : !cases.data.items.length ? <p className="muted">No mutants in this group.</p> : cases.data.items.map(item => <MutantRow key={item.id} item={item} runId={runId} />)}
  </div>;
}

function MutantRow({ item, runId }: { item: MutationCase; runId: string }) {
  const client = useQueryClient();
  const [note, setNote] = useState(item.note);
  const mark = useMutation({ mutationFn: (value: boolean) => qualityApi.markEquivalent(item.id, value, note),
    onSuccess: result => { toast.success(result.case.status === 'equivalent' ? 'Marked as equivalent; score recomputed.' : 'Equivalence removed.'); void client.invalidateQueries({ queryKey: ['quality-cases', runId] }); void client.invalidateQueries({ queryKey: ['quality-run', runId] }); void client.invalidateQueries({ queryKey: ['quality-overview'] }); },
    onError: error => toast.error(error.message) });
  return <details className={`qa-mutant ${item.status}`}>
    <summary><span className="mono">#{item.ordinal}</span><span className={`qa-badge ${item.status === 'killed' || item.status === 'timeout' ? 'approved' : item.status === 'survived' ? 'requires_revision' : item.status}`}>{label(item.status)}</span>{item.critical && <span className="qa-badge stale">critical</span>}<span className="qa-mutant-title">{item.operator_label}: {item.description}</span><span className="qa-sub">line {item.line ?? '—'}</span></summary>
    <div className="qa-diff"><div><span>Original</span><pre>{item.original_snippet}</pre></div><div><span>Mutant</span><pre>{item.mutated_snippet || '(removed)'}</pre></div></div>
    {item.failure_classification && <p className="qa-sub">Classification: {label(item.failure_classification)}{item.execution_duration_ms != null ? ` · ${Math.round(item.execution_duration_ms)} ms` : ''}{item.attempts > 1 ? ` · ${item.attempts} attempts` : ''}</p>}
    {item.message && <pre className="runtime-message">{item.message}</pre>}
    {item.killing_tests.length > 0 && <div className="qa-tests">{item.killing_tests.map(test => <span key={test.name}>{test.hidden && <LockKeyhole size={11} />}{test.name}<small>{label(test.status)}</small></span>)}</div>}
    {(item.status === 'survived' || item.status === 'equivalent') && <div className="qa-equivalence"><input aria-label="Equivalence note" maxLength={500} placeholder="Why is this mutant equivalent?" value={note} onChange={event => setNote(event.target.value)} />
      {item.status === 'survived' ? <button className="button secondary small" disabled={mark.isPending} onClick={() => mark.mutate(true)}>Mark equivalent</button> : <button className="button secondary small" disabled={mark.isPending} onClick={() => mark.mutate(false)}><RotateCcw size={13} />Unmark</button>}</div>}
  </details>;
}

function CommunityTab() {
  const client = useQueryClient();
  const community = useQuery({ queryKey: ['quality-community'], queryFn: qualityApi.community });
  const draft = useMutation({ mutationFn: qualityApi.createDraft, onSuccess: problem => { toast.success(`Draft problem ${problem.slug} created. Run validation next.`); void client.invalidateQueries({ queryKey: ['quality-community'] }); void client.invalidateQueries({ queryKey: ['quality-overview'] }); }, onError: error => toast.error(error.message) });
  const [selected, setSelected] = useState<string | null>(null);
  if (community.isPending) return <Loading label="Loading community submissions…" />;
  if (community.isError) return <ErrorState error={community.error} retry={() => void community.refetch()} />;
  if (!community.data.items.length) return <EmptyState icon={<ShieldCheck size={28} />} title="No approved submissions"><p>Approve a community submission in the <Link className="text-link" to="/admin">submission queue</Link> to turn it into a draft.</p></EmptyState>;
  return <>
    <p className="muted qa-note">Approved submissions become draft problems. A draft is published only after its current version passes the quality gate.</p>
    <div className="qa-table-wrap"><table className="qa-table"><thead><tr><th>SUBMISSION</th><th>LANGUAGE</th><th>TESTS</th><th>DRAFT</th><th aria-label="Actions" /></tr></thead><tbody>
      {community.data.items.map(item => <tr key={item.id}>
        <td><strong className="qa-title">{item.title}</strong><span className="qa-sub">by {item.author_username} · {label(item.category)} · {dateLabel(item.created_at)}</span></td>
        <td>{languageNames[item.language as Language] ?? item.language}</td><td className="mono">{item.test_case_count}</td>
        <td>{item.problem ? <span className="qa-sub">{item.problem.slug} · {item.problem.visibility} · <QualityBadge status={item.problem.quality_status} /></span> : <span className="muted">Not created</span>}</td>
        <td>{item.problem ? <button className="button secondary small" onClick={() => setSelected(selected === item.problem!.slug ? null : item.problem!.slug)}>{selected === item.problem.slug ? 'Close' : 'Validate'}</button> : <button className="button primary small" disabled={draft.isPending} onClick={() => draft.mutate(item.id)}>Create draft</button>}</td>
      </tr>)}
    </tbody></table></div>
    {selected && <ProblemQuality key={selected} slug={selected} onClose={() => setSelected(null)} />}
  </>;
}

function GatesTab() {
  const gates = useQuery({ queryKey: ['quality-gates'], queryFn: qualityApi.gates });
  const [category, setCategory] = useState('default');
  if (gates.isPending) return <Loading label="Loading quality gates…" />;
  if (gates.isError) return <ErrorState error={gates.error} retry={() => void gates.refetch()} />;
  return <div className="qa-gates">
    <p className="muted qa-note">Thresholds apply in order: built-in defaults, then the <strong>default</strong> override, then a category override. Each run records the thresholds it used.</p>
    <div className="qa-filter-chips" role="group" aria-label="Gate category">{['default', ...gates.data.categories].map(value => <button key={value} className={category === value ? 'active' : ''} onClick={() => setCategory(value)}>{label(value)}{gates.data.overrides.some(row => row.category === value) && ' •'}</button>)}</div>
    <GateEditor key={category} category={category} config={gates.data} />
  </div>;
}

function GateEditor({ category, config }: { category: string; config: GateConfig }) {
  const client = useQueryClient();
  const base: Thresholds = category === 'default' ? config.defaults : config.effective.default;
  const [values, setValues] = useState<Thresholds>(() => ({ ...config.effective[category] }));
  const override = config.overrides.find(row => row.category === category);
  const save = useMutation({ mutationFn: () => qualityApi.saveGate(category, Object.fromEntries(Object.entries(values).filter(([key, value]) => value !== base[key]))),
    onSuccess: () => { toast.success('Quality gate saved.'); void client.invalidateQueries({ queryKey: ['quality-gates'] }); }, onError: error => toast.error(error.message) });
  const reset = useMutation({ mutationFn: () => qualityApi.resetGate(category),
    onSuccess: () => { toast.success('Override removed.'); void client.invalidateQueries({ queryKey: ['quality-gates'] }); }, onError: error => toast.error(error.message) });
  return <form className="surface qa-gate-form" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <div className="qa-gate-fields">{Object.entries(config.schema).map(([key, schema]) => <label key={key} className={schema.type === 'bool' ? 'qa-check' : ''}>
      {schema.type === 'bool' ? <><input type="checkbox" checked={Boolean(values[key])} onChange={event => setValues(current => ({ ...current, [key]: event.target.checked }))} />{label(key)}</>
        : <>{label(key)}<input type="number" step={schema.type === 'float' ? 0.5 : 1} min={schema.min ?? undefined} max={schema.max ?? undefined} value={Number(values[key])} onChange={event => setValues(current => ({ ...current, [key]: Number(event.target.value) }))} /></>}
      {values[key] !== base[key] && <small className="qa-changed">override</small>}
    </label>)}</div>
    <div className="qa-actions"><span className="qa-sub">{override ? `Override updated ${dateLabel(override.updated_at)}` : 'No override for this category.'}</span>{override && <button type="button" className="button secondary small" disabled={reset.isPending} onClick={() => reset.mutate()}>Remove override</button>}<button className="button primary small" disabled={save.isPending}>Save thresholds</button></div>
  </form>;
}
