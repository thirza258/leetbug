import { ArrowLeft, ArrowRight, Award, ClipboardCheck, Clock3, Download, FileWarning, Hourglass, Info, ListChecks, Stethoscope, Target } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { ApiError } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { EmptyState, ErrorState, Loading, SignInCard } from '../../components/ui';
import { exportUrl, getReport } from './api';
import { dimensionNames, minutes, score, sessionNames, typeNames, when } from './format';
import { ScoreBar } from './shared';
import type { AssessmentReport, Dimension } from './types';
import './assessments.css';

const dimensions = Object.keys(dimensionNames) as Dimension[];

export default function AssessmentReportPage() {
  const { id = '' } = useParams();
  const { user, loading } = useAuth();
  const query = useQuery({ queryKey: ['assessment-report', id, user?.id], queryFn: () => getReport(id), enabled: !!user,
    refetchInterval: current => current.state.data?.level === 'finalizing' ? 3000 : false });
  if (loading) return <Loading />;
  if (!user) return <div className="page"><SignInCard title="Sign in to view this report" /></div>;
  if (query.isPending) return <Loading label="Opening the report…" />;
  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 409) {
      return <div className="page"><EmptyState icon={<Hourglass size={28} />} title="This session is still running"><p>{query.error.message}</p><Link className="button primary" to={`/assessment-sessions/${id}`}>Return to the session <ArrowRight size={15} /></Link></EmptyState></div>;
    }
    return <div className="page"><ErrorState error={query.error} retry={() => void query.refetch()} /></div>;
  }
  const report = query.data;
  if (report.level === 'finalizing') return <div className="page"><EmptyState icon={<Hourglass size={28} />} title="Scoring your session"><p>{report.pending_evaluations ? `${report.pending_evaluations} evaluation(s) are still running. The report appears as soon as they finish.` : 'Your report is being prepared.'}</p><Loading label="Waiting for the final results…" /></EmptyState></div>;
  if (report.level === 'pending_review') return <div className="page"><EmptyState icon={<ClipboardCheck size={28} />} title="Results pending review"><p>{report.summary?.assessment?.title} is complete. {report.disclaimers?.[0]}</p><Link className="button secondary" to="/assessments">Back to assessments</Link></EmptyState></div>;
  return <ReportView id={id} report={report} />;
}

function ReportView({ id, report }: { id: string; report: AssessmentReport }) {
  const summary = report.summary!;
  const full = report.level === 'full';
  return <div className="page asm-report">
    <Link to="/assessments" className="text-link"><ArrowLeft size={15} /> Assessments</Link>
    <div className="asm-report-head">
      <div><span className="small-tag">{summary.assessment?.type ? typeNames[summary.assessment.type] : 'Assessment'}</span><h1>{summary.assessment?.title}</h1>
        <p className="muted">{summary.candidate?.username ? `@${summary.candidate.username} · ` : ''}{summary.status ? sessionNames[summary.status] : ''} · evaluated {when(summary.evaluated_at)}{report.report_version && report.report_version > 1 ? ` · corrected (v${report.report_version})` : ''}</p></div>
      <div className="asm-export" aria-label="Export report">{(['json', 'csv', 'md'] as const).map(format => <a key={format} className="button secondary small" href={exportUrl(id, format)} download><Download size={13} />{format.toUpperCase()}</a>)}</div>
    </div>
    <div className="stat-grid">{[
      { label: 'Total score', value: score(summary.total_score), detail: full ? 'Weighted across all challenges' : 'Across all challenges', icon: Award },
      { label: 'Challenges solved', value: `${summary.challenges_completed ?? 0}/${summary.challenges_total ?? 0}`, detail: 'Accepted against hidden tests', icon: ListChecks },
      { label: 'Time spent', value: minutes(summary.time_spent_seconds ?? 0), detail: summary.duration_seconds ? `of ${minutes(summary.duration_seconds)} available` : '', icon: Clock3 },
      { label: 'Diagnosis accuracy', value: full ? score(report.behavior?.diagnosis_accuracy) : '—', detail: full ? `${Math.round((report.behavior?.diagnosis_coverage ?? 0) * 100)}% of challenges diagnosed` : 'Shown in the full report', icon: Stethoscope },
    ].map(({ label, value, detail, icon: Icon }) => <div className="stat-card" key={label}><span className="stat-icon purple"><Icon size={19} /></span><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>)}</div>
    <section className="surface asm-section"><div className="surface-heading"><h2>Challenges</h2><Target size={17} /></div>
      <div className="history-table-wrap"><table className="data-table asm-challenge-table"><thead><tr><th>#</th><th>CHALLENGE</th><th>STATUS</th>{full && dimensions.map(name => <th key={name}>{dimensionNames[name].toUpperCase()}</th>)}<th>SCORE</th></tr></thead><tbody>
        {report.challenges?.map(row => <tr key={row.position}><td>{row.position}</td><td><strong>{row.title}</strong>{full && row.time_spent_seconds != null && <div className="muted">{row.submissions} submissions · {minutes(row.time_spent_seconds)}{row.corrected ? ' · corrected' : ''}</div>}</td>
          <td><span className={`asm-status ${row.status}`}>{row.status.replace('_', ' ')}</span></td>
          {full && dimensions.map(name => <td key={name} className="mono">{row.components?.[name] == null ? '—' : Math.round(row.components[name]!)}</td>)}
          <td className="mono"><strong>{Math.round(row.total)}</strong></td></tr>)}
      </tbody></table></div></section>
    {full && <div className="progress-columns">
      <section className="surface asm-section"><div className="surface-heading"><h2>Competency breakdown</h2></div>
        <div className="asm-competencies">{report.competencies?.map(row => <ScoreBar key={row.id} label={row.name} value={row.score} detail={row.assessed ? `${row.evidence_count} challenge(s) of evidence` : 'Not assessed in this session'} />)}</div>
        {report.profile && report.profile.score != null && <p className="muted asm-profile">Role profile match: <strong>{score(report.profile.score)}</strong> ({Math.round(report.profile.coverage * 100)}% of profile skills assessed)</p>}</section>
      <section className="surface asm-section"><div className="surface-heading"><h2>How you worked</h2></div>
        {report.behavior && <dl className="asm-facts stacked">
          <div><dt>Submissions</dt><dd>{report.behavior.submissions} full · {report.behavior.runs} test runs ({report.behavior.avg_submissions_per_challenge} per started challenge)</dd></div>
          <div><dt>Average time per challenge</dt><dd>{report.behavior.avg_time_per_challenge_seconds == null ? '—' : minutes(report.behavior.avg_time_per_challenge_seconds)}</dd></div>
          <div><dt>Hints used</dt><dd>{report.behavior.hints_used}</dd></div>
          <div><dt>AI assistance</dt><dd>{report.behavior.ai_interactions} interactions · {report.behavior.ai_submissions} AI patches</dd></div>
          <div><dt>Failed submissions</dt><dd>{Object.entries(report.behavior.failed_test_patterns).map(([status, count]) => `${count} ${status.replace('_', ' ')}`).join(', ') || 'None'}</dd></div>
          <div><dt>Explanations</dt><dd>{report.behavior.explanations_submitted} submitted{report.behavior.explanation_quality != null ? ` · ${score(report.behavior.explanation_quality)} quality` : ''}</dd></div>
        </dl>}</section>
    </div>}
    {full && !!report.development_areas?.length && <section className="surface asm-section"><div className="surface-heading"><h2>Recommended development areas</h2></div>
      <div className="asm-areas">{report.development_areas.map(area => <article key={area.id}><strong>{area.area}</strong><p>{area.evidence}</p><p>{area.recommendation}</p>
        {area.practice.length > 0 && <div className="asm-practice">{area.practice.map(item => <Link key={item.slug} to={`/problems/${item.slug}`}>{item.title}<ArrowRight size={12} /></Link>)}</div>}</article>)}</div></section>}
    {full && !!report.corrections?.length && <section className="surface asm-section"><div className="surface-heading"><h2>Corrections</h2><FileWarning size={17} /></div>
      <ul className="asm-rules">{report.corrections.map(row => <li key={row.report_version}><Info size={14} />Version {row.report_version} · {when(row.at)}: {row.reason} ({score(row.before_total)} → {score(row.after_total)})</li>)}</ul></section>}
    <section className="surface asm-section asm-notes"><div className="surface-heading"><h2>How to read this report</h2><Info size={17} /></div>
      <ul className="asm-rules">{report.disclaimers?.map(note => <li key={note}><Info size={14} />{note}</li>)}</ul></section>
  </div>;
}
