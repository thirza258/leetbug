import { Activity, Database, RefreshCw, Server } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../lib/auth';
import { languageNames, ms } from '../../lib/constants';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import type { Language } from '../../types';
import { label, qualityApi } from './api';
import type { AdminMetrics, Percentiles } from './types';
import './quality.css';

export default function MetricsAdminPage() {
  const { user, loading } = useAuth();
  const [days, setDays] = useState(7);
  const [minSamples, setMinSamples] = useState(20);
  const [page, setPage] = useState(1);
  const admin = !!user?.is_admin;
  const metrics = useQuery({ queryKey: ['admin-metrics', days], queryFn: () => qualityApi.metrics(days), enabled: admin, refetchInterval: 30_000 });
  const calibration = useQuery({ queryKey: ['admin-calibration', minSamples, page], queryFn: () => qualityApi.calibration(minSamples, page), enabled: admin });
  if (loading) return <Loading />;
  if (!admin) return <div className="page"><EmptyState title="Admin access required"><p>This page is restricted to administrators.</p><Link className="button primary" to="/">Back to library</Link></EmptyState></div>;
  return <div className="page qa-page">
    <PageHeading eyebrow="ADMIN" title="Platform health" description="Queues, execution and AI latency, failure rates, and difficulty calibration from recorded activity."
      action={<div className="qa-actions"><select aria-label="Time window" value={days} onChange={event => setDays(Number(event.target.value))}><option value={1}>Last 24 hours</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option></select><button className="button secondary small" onClick={() => { void metrics.refetch(); void calibration.refetch(); }}><RefreshCw size={13} />Refresh</button></div>} />
    {metrics.isPending ? <Loading label="Collecting metrics…" /> : metrics.isError ? <ErrorState error={metrics.error} retry={() => void metrics.refetch()} /> : <Health data={metrics.data} />}
    <section className="surface qa-section"><div className="surface-heading"><h2>Difficulty calibration</h2><label className="qa-inline">Minimum learners<input type="number" min={5} max={1000} value={minSamples} onChange={event => { setPage(1); setMinSamples(Math.max(5, Number(event.target.value) || 5)); }} /></label></div>
      {calibration.isPending ? <Loading label="Analyzing attempts…" /> : calibration.isError ? <ErrorState error={calibration.error} /> : !calibration.data.items.length ? <p className="muted">No practice attempts recorded yet.</p> : <>
        <p className="muted qa-note">{calibration.data.note}</p>
        <div className="qa-table-wrap"><table className="qa-table qa-dense"><thead><tr><th>PROBLEM</th><th>LABEL</th><th>LEARNERS</th><th>SOLVED</th><th>MEDIAN TIME</th><th>SUBMITS</th><th>DIAGNOSIS</th><th>HINTS</th><th>ABANDONED</th><th>HIDDEN FAIL</th><th>AI</th><th>SUGGESTION</th></tr></thead><tbody>
          {calibration.data.items.map(item => <tr key={item.problem_id}>
            <td><strong className="qa-title">{item.title}</strong><span className="qa-sub">{item.slug} · {label(item.confidence)} confidence</span></td>
            <td>{item.difficulty}<span className="qa-sub">{item.estimated_minutes} min</span></td>
            <td className="mono">{item.samples}</td><td className="mono">{rate(item.solve_rate)}</td>
            <td className="mono">{item.median_solve_seconds == null ? '—' : `${(item.median_solve_seconds / 60).toFixed(1)} min`}</td>
            <td className="mono">{item.avg_submissions ?? '—'}</td><td className="mono">{item.diagnosis_accuracy ?? '—'}</td>
            <td className="mono">{rate(item.hint_usage_rate)}</td><td className="mono">{rate(item.abandonment_rate)}</td>
            <td className="mono">{rate(item.hidden_failure_rate)}</td><td className="mono">{rate(item.ai_dependency_rate)}</td>
            <td>{item.suggestion ? <span className={`qa-badge ${item.suggestion.direction === 'consistent' ? 'approved' : 'stale'}`} title={item.suggestion.reason}>{item.suggestion.direction === 'consistent' ? 'consistent' : `→ ${item.suggestion.difficulty}`}</span> : <span className="muted">needs {calibration.data.min_samples}+</span>}</td>
          </tr>)}
        </tbody></table></div>
        {calibration.data.pages > 1 && <div className="catalog-footer"><span>{calibration.data.total} problems</span><div className="pagination"><button className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button><span>{page}</span><button className="icon-button" aria-label="Next page" disabled={page >= calibration.data.pages} onClick={() => setPage(page + 1)}>›</button></div></div>}
      </>}
    </section>
  </div>;
}

const rate = (value: number | null | undefined) => value == null ? '—' : `${value}%`;

function Health({ data }: { data: AdminMetrics }) {
  const rows: [string, Percentiles][] = [
    ['Execution runtime', data.execution.runtime_ms], ['Submission turnaround', data.execution.turnaround_ms],
    ['Mutant execution', data.mutation.case_duration_ms], ['Quality validation run', data.mutation.validation_duration_ms],
    ['RAG retrieval', data.ai.retrieval_ms], ['AI generation', data.ai.generation_ms], ['AI end to end', data.ai.latency_ms],
    ['Assessment finalization', data.assessments.finalization_latency_ms],
  ];
  const failures: [string, number | null][] = [
    ['Execution service errors', data.execution.service_error_rate], ['Mutant infrastructure errors', data.mutation.infrastructure_error_rate],
    ['Invalid mutants', data.mutation.invalid_rate], ['Mutant timeouts', data.mutation.timeout_rate],
    ['AI assistant errors', data.ai.error_rate], ['AI evaluation failures', data.ai_evaluation.failure_rate],
  ];
  return <>
    <div className="qa-summary">
      <div className={`qa-stat ${data.health.database === 'ok' ? 'green' : 'coral'}`}><span><Database size={13} /> Database</span><strong>{data.health.database}</strong></div>
      <div className={`qa-stat ${data.health.redis === 'ok' ? 'green' : 'coral'}`}><span><Server size={13} /> Redis</span><strong>{data.health.redis}</strong></div>
      {Object.entries(data.queues).map(([queue, depth]) => <div className="qa-stat" key={queue}><span>Queue · {queue}</span><strong>{depth ?? '—'}</strong><small>waiting jobs</small></div>)}
      <div className="qa-stat"><span><Activity size={13} /> In progress</span><strong>{Object.values(data.jobs_in_progress).reduce((sum, value) => sum + value, 0)}</strong><small>{Object.entries(data.jobs_in_progress).filter(([, value]) => value).map(([key, value]) => `${value} ${label(key)}`).join(' · ') || 'idle'}</small></div>
      <div className={`qa-stat ${data.sandbox.orphaned_containers ? 'coral' : ''}`}><span>Orphaned sandboxes</span><strong>{data.sandbox.orphaned_containers ?? '—'}</strong><small>{data.sandbox.observed_at ? `observed ${new Date(data.sandbox.observed_at).toLocaleString()}` : data.sandbox.note}</small></div>
    </div>
    <div className="qa-grid">
      <section className="surface qa-section"><div className="surface-heading"><h2>Latency percentiles</h2><span className="small-tag">{data.window_days} DAYS</span></div>
        <div className="qa-table-wrap"><table className="qa-table qa-dense"><thead><tr><th>MEASURE</th><th>P50</th><th>P95</th><th>P99</th><th>SAMPLES</th></tr></thead><tbody>
          {rows.map(([name, value]) => <tr key={name}><td>{name}</td><td className="mono">{ms(value.p50)}</td><td className="mono">{ms(value.p95)}</td><td className="mono">{ms(value.p99)}</td><td className="mono">{value.samples}</td></tr>)}
        </tbody></table></div>
      </section>
      <section className="surface qa-section"><div className="surface-heading"><h2>Failure rates</h2></div>
        <ul className="qa-rates">{failures.map(([name, value]) => <li key={name}><span>{name}</span><strong className={value ? 'coral' : ''}>{rate(value)}</strong></li>)}</ul>
        <p className="qa-sub">{data.execution.evaluations} evaluations · {data.mutation.cases} mutants · {data.ai.interactions} AI requests · {data.assessments.finalized} finalized assessments · {data.mutation.approved_runs} approved quality runs</p>
      </section>
    </div>
    {Object.keys(data.execution.by_language).length > 0 && <section className="surface qa-section"><div className="surface-heading"><h2>Execution by language</h2></div>
      <div className="qa-table-wrap"><table className="qa-table qa-dense"><thead><tr><th>LANGUAGE</th><th>RUNTIME P50</th><th>RUNTIME P95</th><th>TURNAROUND P95</th><th>SAMPLES</th></tr></thead><tbody>
        {Object.entries(data.execution.by_language).map(([language, value]) => <tr key={language}><td>{languageNames[language as Language] ?? language}</td><td className="mono">{ms(value.runtime_ms.p50)}</td><td className="mono">{ms(value.runtime_ms.p95)}</td><td className="mono">{ms(value.turnaround_ms.p95)}</td><td className="mono">{value.runtime_ms.samples}</td></tr>)}
      </tbody></table></div>
    </section>}
  </>;
}
