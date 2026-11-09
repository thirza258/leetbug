import { ArrowRight, ClipboardCheck, History, ShieldCheck } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../../lib/auth';
import { languageNames } from '../../lib/constants';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import { listAssessments, mySessions } from './api';
import { score, sessionNames, typeNames, when } from './format';
import { PolicyBadges } from './shared';
import type { AssessmentCard } from './types';
import './assessments.css';

export default function AssessmentsPage() {
  const { user } = useAuth();
  const list = useQuery({ queryKey: ['assessments', user?.id], queryFn: listAssessments });
  const history = useQuery({ queryKey: ['assessment-history', user?.id], queryFn: mySessions, enabled: !!user });
  return <div className="page">
    <PageHeading eyebrow="PROVE IT UNDER THE CLOCK" title="Assessments" description="Timed, structured debugging assessments. Diagnose the root cause, ship a verified fix, and get a competency report." action={user?.is_admin ? <Link className="button secondary" to="/admin/assessments"><ShieldCheck size={15} />Manage assessments</Link> : undefined} />
    {list.isPending ? <Loading label="Loading assessments…" /> : list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} />
      : !list.data.items.length ? <EmptyState icon={<ClipboardCheck size={28} />} title="No assessments are open"><p>Check back soon, or ask an organizer for an invitation.</p></EmptyState>
      : <div className="asm-card-grid">{list.data.items.map(item => <AssessmentTile key={item.id} item={item} />)}</div>}
    {user && <section className="surface asm-history" aria-labelledby="assessment-history">
      <div className="surface-heading"><h2 id="assessment-history">Your assessment history</h2><History size={17} /></div>
      {history.isPending ? <Loading /> : history.isError ? <ErrorState error={history.error} /> : !history.data.items.length
        ? <p className="muted">Sessions you start appear here with their reports.</p>
        : <div className="history-table-wrap"><table className="data-table"><thead><tr><th>ASSESSMENT</th><th>STATUS</th><th>STARTED</th><th>SCORE</th><th aria-label="Actions" /></tr></thead><tbody>
          {history.data.items.map(row => <tr key={row.id}><td><strong>{row.assessment.title}</strong><div className="muted">{typeNames[row.assessment.assessment_type]} · {row.challenge_count} challenges</div></td>
            <td><span className={`asm-status ${row.status}`}>{sessionNames[row.status]}</span></td><td>{when(row.started_at)}</td>
            <td>{row.released ? score(row.total_score) : row.status === 'active' ? '—' : 'Pending review'}</td>
            <td>{row.status === 'active' ? <Link className="button primary small" to={`/assessment-sessions/${row.id}`}>Resume <ArrowRight size={13} /></Link> : <Link className="button secondary small" to={`/assessment-sessions/${row.id}/report`}>Report</Link>}</td></tr>)}
        </tbody></table></div>}
    </section>}
  </div>;
}

function AssessmentTile({ item }: { item: AssessmentCard }) {
  const active = item.my_session?.status === 'active';
  return <article className="surface asm-tile">
    <div className="asm-tile-top"><span className="small-tag">{typeNames[item.assessment_type]}</span>{item.visibility !== 'public' && <span className="small-tag">Invitation</span>}</div>
    <h2><Link to={`/assessments/${item.slug}`}>{item.title}</Link></h2>
    <p className="muted">{item.description}</p>
    <PolicyBadges policy={item.assistance_policy} duration={item.duration_seconds} />
    <dl className="asm-facts"><div><dt>Challenges</dt><dd>{item.challenge_count}</dd></div><div><dt>Difficulty</dt><dd>{item.difficulty_mix.easy} easy · {item.difficulty_mix.medium} medium · {item.difficulty_mix.hard} hard</dd></div><div><dt>Languages</dt><dd>{item.languages.map(language => languageNames[language] ?? language).join(', ')}</dd></div></dl>
    <div className="asm-tile-actions">{active ? <Link className="button primary small" to={`/assessment-sessions/${item.my_session!.id}`}>Resume session <ArrowRight size={13} /></Link> : <Link className="button secondary small" to={`/assessments/${item.slug}`}>View details <ArrowRight size={13} /></Link>}
      {item.my_session && !active && <Link className="text-link" to={`/assessment-sessions/${item.my_session.id}/report`}>Last report</Link>}</div>
  </article>;
}
