import { ArrowRight, Brain, ClipboardCheck, Compass, History, Siren, TrendingUp } from 'lucide-react';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { ErrorState, Loading } from '../../components/ui';
import { formatScore } from './api';
import type { Page, Status } from '../../types';
import { StatusBadge } from '../../components/ui';
import { LevelPill } from './parts';
import type { Confidence, DiagnosisHistoryItem, Insights, MasteryRow } from './types';
import './diagnosis.css';

const confidenceLabels: Record<Confidence, string> = {
  insufficient: 'Not enough data', low: 'Provisional', moderate: 'Moderate confidence', high: 'High confidence',
};

// Rendered on the Progress page (PRD 5.4 and 12.3). Scores below the sample-size thresholds
// are labelled provisional rather than presented as a definitive measure.
export default function CompetencyDashboard() {
  const { user } = useAuth();
  const insights = useQuery({ queryKey: ['insights', user?.id], queryFn: () => api<Insights>('/insights/me'), enabled: !!user });
  const history = useQuery({ queryKey: ['diagnosis-history', user?.id],
    queryFn: () => api<Page<DiagnosisHistoryItem>>('/diagnosis/history?limit=8'), enabled: !!user });
  if (!user) return null;
  if (insights.isPending) return <Loading label="Measuring your debugging range…" />;
  if (insights.isError) return <ErrorState error={insights.error} retry={() => void insights.refetch()} />;
  const data = insights.data;
  const reasoning = data.reasoning;
  return <div className="dx-dashboard" aria-label="Debugging competency">
    <div className="dx-dashboard-grid">
      <section className="surface"><div className="surface-heading"><h2>Debugging reasoning</h2><Brain size={17} aria-hidden /></div>
        <div className="dx-hero"><strong>{formatScore(reasoning.score)}</strong><span>/ 100</span>
          <span className={`dx-pill ${reasoning.confidence === 'insufficient' ? 'neutral' : reasoning.provisional ? 'partial' : 'strong'}`}>
            {confidenceLabels[reasoning.confidence]}</span></div>
        <p className="dx-message">{reasoning.message} Based on {reasoning.sample_size} solved challenge{reasoning.sample_size === 1 ? '' : 's'} with a diagnosis.</p>
        <ul className="dx-meters">{reasoning.dimensions.map(dimension => <li key={dimension.id}>
          <div className="dx-meter-label"><span>{dimension.name}</span><span>{formatScore(dimension.score)}</span></div>
          <Meter value={dimension.score} label={dimension.name} />
        </li>)}</ul>
      </section>
      <section className="surface"><div className="surface-heading"><h2>Diagnosis quality over time</h2><TrendingUp size={17} aria-hidden /></div>
        <p className="dx-message">Average diagnosis score per week, last 12 weeks.</p>
        <TrendChart trend={data.trend} />
        <details className="dx-history"><summary>Show as a table</summary><div className="dx-table-wrap"><table className="dx-table">
          <thead><tr><th>Week of</th><th>Diagnoses</th><th>Average score</th><th>Submissions</th><th>Pass rate</th></tr></thead>
          <tbody>{data.trend.map(week => <tr key={week.week}><td>{weekLabel(week.week)}</td><td className="num">{week.diagnoses}</td>
            <td className="num">{formatScore(week.diagnosis_score)}</td><td className="num">{week.submissions}</td>
            <td className="num">{week.pass_rate == null ? '—' : `${week.pass_rate}%`}</td></tr>)}</tbody>
        </table></div></details>
      </section>
    </div>
    <div className="dx-tiles">{[
      { label: 'Patch correctness', value: formatScore(data.patch_correctness) },
      { label: 'Engineering quality', value: formatScore(data.engineering_quality) },
      { label: 'Explanation quality', value: formatScore(data.explanation_quality) },
      { label: 'Diagnoses submitted', value: `${data.diagnoses}` },
    ].map(tile => <div key={tile.label}><span>{tile.label}</span><strong>{tile.value}</strong></div>)}</div>
    <section className="surface"><div className="surface-heading"><h2>Skill category mastery</h2><Compass size={17} aria-hidden /></div>
      {data.categories.length ? <MasteryTable rows={data.categories.slice(0, 8)} label="Bug category" />
        : <p className="muted">Attempt a few challenges to see which defect categories you handle best.</p>}
      {data.skills.length > 0 && <div className="dx-chips" aria-label="Debugging skills practiced">{data.skills.slice(0, 8).map(skill =>
        <span key={skill.id}>{skill.name} · {formatScore(skill.mastery)}</span>)}</div>}
    </section>
    <section className="surface"><div className="surface-heading"><h2>Recent diagnoses and patches</h2><History size={17} aria-hidden /></div>
      {history.isError ? <ErrorState error={history.error} /> : !history.data ? <Loading label="Loading history…" /> : history.data.items.length === 0
        ? <p className="muted">Your diagnoses appear here, with the fixes you submitted after each one.</p>
        : <ul className="dx-list">{history.data.items.map(row => <li key={row.id}>
          <Link to={`/problems/${row.problem_slug}`}>{row.problem_title}</Link>
          <span className="muted">Revision {row.revision} · {row.defect_category_name}</span>
          <LevelPill level={row.passed ? 'strong' : (row.score ?? 0) >= 35 ? 'partial' : 'missing'} />
          {row.submissions.slice(-2).map(item => <StatusBadge key={item.id} status={item.status as Status} />)}
          <span>{formatScore(row.score)} / 100</span></li>)}</ul>}
    </section>
    <div className="dx-dashboard-grid">
      <section className="surface"><div className="surface-heading"><h2>Incidents and assessments</h2><Siren size={17} aria-hidden /></div>
        {data.incidents.length === 0 && data.assessments.length === 0 ? <p className="muted">No incident investigations or assessments yet. <Link className="text-link" to="/incidents">Open an incident</Link> or <Link className="text-link" to="/assessments">take an assessment</Link>.</p> :
          <ul className="dx-list">
            {data.incidents.map(row => <li key={row.session_id}><Siren size={14} aria-hidden /><Link to={`/incidents/${row.incident_slug}`}>{row.title}</Link>
              <span className="dx-pill neutral">{row.severity}</span><span>{row.status === 'resolved' ? `Score ${formatScore(row.score)}` : 'In progress'}</span></li>)}
            {data.assessments.map(row => <li key={row.session_id}><ClipboardCheck size={14} aria-hidden />
              <Link to={row.finalized ? `/assessment-sessions/${row.session_id}/report` : `/assessment-sessions/${row.session_id}`}>{row.title}</Link>
              <span>{!row.finalized ? 'In progress' : row.score_hidden ? 'Awaiting review' : `Score ${formatScore(row.score)}`}</span></li>)}
          </ul>}
      </section>
      <section className="surface"><div className="surface-heading"><h2>Recommended next</h2><ArrowRight size={17} aria-hidden /></div>
        {data.recommendations.length ? <ul className="dx-list">{data.recommendations.map(row => <li key={row.slug}>
          <Link to={`/problems/${row.slug}`}>{row.title}</Link><span className="dx-pill neutral">{row.reason}</span><span>{row.difficulty}</span></li>)}</ul>
          : <p className="muted">You have solved every case in your weakest categories. Try an incident next.</p>}
        {data.recommended_concepts.length > 0 && <div className="dx-chips" aria-label="Concepts to review">{data.recommended_concepts.map(concept =>
          <span key={concept.id}>{concept.name}</span>)}</div>}
      </section>
    </div>
  </div>;
}

function Meter({ value, label }: { value: number | null; label: string }) {
  const width = Math.max(0, Math.min(100, value ?? 0));
  return <div className="dx-meter" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100}
    aria-valuenow={value == null ? undefined : Math.round(value)} aria-valuetext={value == null ? 'No data yet' : `${Math.round(value)} of 100`}>
    <span style={{ width: `${width}%` }} />
  </div>;
}

function MasteryTable({ rows, label }: { rows: MasteryRow[]; label: string }) {
  return <div className="dx-table-wrap"><table className="dx-table">
    <thead><tr><th>{label}</th><th>Attempted</th><th>Solved</th><th>Diagnosis</th><th>Mastery</th><th>Confidence</th></tr></thead>
    <tbody>{rows.map(row => <tr key={row.id}><td>{row.name}</td><td className="num">{row.attempted}</td><td className="num">{row.solved}</td>
      <td className="num">{formatScore(row.diagnosis_score)}</td>
      <td><div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Meter value={row.mastery} label={`${row.name} mastery`} /><span className="num">{formatScore(row.mastery)}</span></div></td>
      <td>{confidenceLabels[row.confidence]}</td></tr>)}</tbody>
  </table></div>;
}

function weekLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// Single series, magnitude 0–100: one accent hue, thin bars with rounded data ends anchored to the
// baseline, recessive grid, and a per-bar hover/focus readout. The table above is the accessible view.
function TrendChart({ trend }: { trend: Insights['trend'] }) {
  const [active, setActive] = useState<number | null>(null);
  const width = 600, height = 170, left = 30, right = 8, top = 10, bottom = 24;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const slot = plotWidth / Math.max(1, trend.length);
  const barWidth = Math.min(24, slot - 2);
  const y = (value: number) => top + plotHeight - (value / 100) * plotHeight;
  const point = active == null ? null : trend[active];
  return <>
    <svg className="dx-chart" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Weekly average diagnosis score">
      {[0, 50, 100].map(tick => <g key={tick}><line className="grid" x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
        <text className="axis" x={left - 6} y={y(tick) + 3} textAnchor="end">{tick}</text></g>)}
      {trend.map((week, index) => {
        const x = left + index * slot + (slot - barWidth) / 2;
        const value = week.diagnosis_score;
        const barTop = value == null ? y(0) : y(value);
        const radius = Math.min(4, Math.max(0, y(0) - barTop));
        const path = value == null || value <= 0 ? null
          : `M${x},${y(0)} V${barTop + radius} Q${x},${barTop} ${x + radius},${barTop} H${x + barWidth - radius} Q${x + barWidth},${barTop} ${x + barWidth},${barTop + radius} V${y(0)} Z`;
        const description = `Week of ${weekLabel(week.week)}: ${value == null ? 'no diagnoses' : `average ${Math.round(value)} from ${week.diagnoses} diagnos${week.diagnoses === 1 ? 'is' : 'es'}`}`;
        return <g key={week.week} tabIndex={0} role="img" aria-label={description}
          onMouseEnter={() => setActive(index)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)}>
          <rect className="hit" x={left + index * slot} y={top} width={slot} height={plotHeight} />
          {path && <path className="bar" d={path} />}
          {index % 3 === 0 && <text className="axis" x={x + barWidth / 2} y={height - 6} textAnchor="middle">{weekLabel(week.week)}</text>}
        </g>;
      })}
    </svg>
    <p className="dx-chart-note" aria-live="polite">{point ? `Week of ${weekLabel(point.week)}: ${point.diagnosis_score == null ? 'no diagnoses' : `average diagnosis ${Math.round(point.diagnosis_score)} from ${point.diagnoses}`}${point.submissions ? ` · ${point.submissions} full submissions, ${point.pass_rate}% passed` : ''}` : 'Hover or focus a week for details.'}</p>
  </>;
}
