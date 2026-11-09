import { ArrowRight, CheckCircle2, Clock3, FileSearch, Layers, Server, Siren } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../lib/auth';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import { incidentKeys, listIncidents } from './api';
import IncidentAdmin from './IncidentAdmin';
import { levelNames, score, severityTone } from './format';
import type { IncidentListItem } from './types';
import './incidents.css';

export default function IncidentsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const level = Number(params.get('level') || 0);
  const query = useQuery({ queryKey: incidentKeys.list(user?.id), queryFn: listIncidents });
  const items = (query.data?.items ?? []).filter(item => !level || item.level === level);
  return <div className="page incidents-page">
    <PageHeading eyebrow="SIMULATE PRODUCTION" title="Production incidents"
      description="Investigate fictional production failures with logs, metrics, traces, data and recent changes. Diagnose the root cause, ship a fix, prove it with regression tests, and write the resolution."
      action={!user ? <Link className="button primary" to="/login?next=/incidents">Sign in to investigate <ArrowRight size={15} /></Link> : undefined} />
    <div className="incident-level-filter" role="group" aria-label="Filter by difficulty level">
      {[0, 1, 2, 3, 4].map(value => <button key={value} className={level === value ? 'active' : ''} aria-pressed={level === value}
        onClick={() => setParams(value ? { level: String(value) } : {}, { replace: true })}>
        {value ? `Level ${value} · ${levelNames[value]}` : 'All levels'}</button>)}
    </div>
    {query.isPending ? <Loading label="Paging the on-call engineer…" /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} />
      : !items.length ? <EmptyState icon={<Siren size={28} />} title="No incidents match this level"><p>Choose another level to see more scenarios.</p></EmptyState>
        : <div className="incident-grid">{items.map(item => <IncidentCard key={item.slug} item={item} />)}</div>}
    {user?.is_admin && <IncidentAdmin />}
  </div>;
}

function IncidentCard({ item }: { item: IncidentListItem }) {
  const session = item.my_session;
  const state = !session ? 'Not started' : session.status === 'resolved' ? 'Resolved' : 'In progress';
  return <Link to={`/incidents/${item.slug}`} className="incident-card surface">
    <div className="incident-card-top">
      <span className={`incident-severity ${severityTone[item.severity]}`}>{item.severity}</span>
      <span className="incident-level"><Layers size={13} />Level {item.level}</span>
      {item.status === 'draft' && <span className="small-tag">DRAFT</span>}
    </div>
    <h2>{item.title}</h2>
    <p>{item.summary}</p>
    <div className="incident-chips">
      <span className="category-pill purple">{item.category.name}</span>
      {item.affected_services.slice(0, 3).map(service => <span key={service} className="incident-service"><Server size={11} />{service}</span>)}
    </div>
    <div className="incident-card-footer">
      <span><Clock3 size={13} />{item.estimated_minutes ?? '—'} min</span>
      <span><FileSearch size={13} />{item.artifact_count} artifacts</span>
      <span className={`incident-state ${session?.status ?? 'todo'}`}>{session?.status === 'resolved' && <CheckCircle2 size={13} />}{state}{item.best_score != null && ` · ${score(item.best_score)}/100`}</span>
    </div>
  </Link>;
}
