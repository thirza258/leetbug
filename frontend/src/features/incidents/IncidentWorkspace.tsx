import { AlertTriangle, ArrowLeft, Bug, CalendarClock, CheckCircle2, ChevronRight, Code2, Eye, FileSearch, Gauge, Layers, LoaderCircle, Play, RefreshCw, Server, Siren, Target } from 'lucide-react';
import { useCallback, useRef } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import { ErrorState, Loading } from '../../components/ui';
import ArtifactBrowser from './ArtifactBrowser';
import DebugPanel from './DebugPanel';
import ResolutionPanel from './ResolutionPanel';
import { getIncident, getSession, incidentKeys, recordView, startSession } from './api';
import { clock, contextTypes, dimensionNames, dimensionOrder, levelNames, observabilityTypes, score, severityTone, timelineNames } from './format';
import type { Artifact, IncidentOverview, SessionPayload } from './types';
import './incidents.css';

type Tab = 'overview' | 'observability' | 'context' | 'debug' | 'resolution';
const TABS: { id: Tab; label: string; icon: typeof Eye }[] = [
  { id: 'overview', label: 'Overview', icon: Siren }, { id: 'observability', label: 'Observability', icon: Gauge },
  { id: 'context', label: 'System context', icon: Server }, { id: 'debug', label: 'Debug', icon: Code2 },
  { id: 'resolution', label: 'Resolution', icon: Target },
];

export default function IncidentWorkspace() {
  const { slug = '' } = useParams();
  const { user, loading } = useAuth();
  const client = useQueryClient();
  const overview = useQuery({ queryKey: incidentKeys.overview(slug, user?.id), queryFn: () => getIncident(slug), enabled: !loading });
  const sessionId = overview.data?.my_session?.id;
  const session = useQuery({ queryKey: incidentKeys.session(sessionId), queryFn: () => getSession(sessionId!), enabled: !!sessionId && !!user,
    refetchInterval: query => query.state.data?.resolutions.some(row => row.status === 'queued' || row.status === 'running') ? 1500 : false });
  const start = useMutation({ mutationFn: () => startSession(slug), onSuccess: payload => {
    client.setQueryData(incidentKeys.session(payload.session.id), payload);
    void client.invalidateQueries({ queryKey: ['incident', slug] });
    void client.invalidateQueries({ queryKey: ['incidents'] });
  }, onError: error => toast.error(error.message) });
  if (loading || overview.isPending) return <Loading label="Opening the incident…" />;
  if (overview.isError) return <div className="page"><ErrorState error={overview.error} retry={() => void overview.refetch()} /></div>;
  const incident = overview.data;
  const active = incident.my_session;
  const startButton = !user ? <Link className="button primary" to={`/login?next=${encodeURIComponent(`/incidents/${slug}`)}`}>Sign in to investigate</Link>
    : <button className="button primary" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? <LoaderCircle size={14} className="spin" /> : active?.status === 'resolved' ? <RefreshCw size={14} /> : <Play size={14} />}{active?.status === 'resolved' ? 'Start a new investigation' : 'Start investigation'}</button>;
  return <div className="incident-page">
    <div className="workspace-heading"><Link to="/incidents" className="text-link"><ArrowLeft size={15} /> Incidents</Link><ChevronRight size={14} /><span>{incident.severity} · Level {incident.level}</span>
      <div className="workspace-heading-right">{active && <span className={`incident-state ${active.status}`}>{active.status === 'resolved' ? <><CheckCircle2 size={13} />Resolved · {score(active.score)}/100</> : 'Investigation in progress'}</span>}</div></div>
    <header className="incident-header surface">
      <div className="incident-card-top"><span className={`incident-severity ${severityTone[incident.severity]}`}>{incident.severity}</span><span className="incident-level"><Layers size={13} />Level {incident.level} · {levelNames[incident.level]}</span><span className="category-pill purple">{incident.category.name}</span>{incident.status === 'draft' && <span className="small-tag">DRAFT</span>}</div>
      <h1>{incident.title}</h1>
      <p>{incident.summary}</p>
      <div className="incident-chips">{incident.affected_services.map(service => <span key={service} className="incident-service"><Server size={11} />{service}</span>)}<span className="incident-service"><CalendarClock size={11} />{incident.estimated_minutes} min</span></div>
      {(!active || active.status !== 'active') && <div className="incident-start">{startButton}<span className="muted">Your session, artifact views and scores are private to you.</span></div>}
    </header>
    {!sessionId || !user ? <OverviewPanel incident={incident} />
      : session.isPending ? <Loading label="Restoring your investigation…" />
        : session.isError ? <ErrorState error={session.error} retry={() => void session.refetch()} />
          : <SessionWorkspace key={session.data.session.id} payload={session.data} />}
  </div>;
}

function SessionWorkspace({ payload }: { payload: SessionPayload }) {
  const client = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = (TABS.some(item => item.id === params.get('tab')) ? params.get('tab') : 'overview') as Tab;
  const recorded = useRef(new Set<string>());
  const sessionId = payload.session.id;
  const refresh = useCallback(() => {
    void client.invalidateQueries({ queryKey: incidentKeys.session(sessionId) });
    void client.invalidateQueries({ queryKey: ['diagnosis'] });
    void client.invalidateQueries({ queryKey: ['incidents'] });
  }, [client, sessionId]);
  const select = (next: Tab) => setParams(previous => { const copy = new URLSearchParams(previous); copy.set('tab', next); return copy; }, { replace: true });
  function open(artifact: Artifact) {
    if (payload.session.status !== 'active' || recorded.current.has(artifact.id)) return;
    recorded.current.add(artifact.id);
    recordView(sessionId, artifact.id).then(result => { if (result.first_view) refresh(); }).catch(() => recorded.current.delete(artifact.id));
  }
  const investigation = payload.session.investigation;
  return <>
    <div className="incident-progress" aria-label="Investigation progress">
      <span><Eye size={13} />{investigation.viewed_types.length}/{investigation.available_types.length} evidence types inspected</span>
      <span><Play size={13} />{investigation.runs} reproduction run{investigation.runs === 1 ? '' : 's'}</span>
      <span><Bug size={13} />{payload.diagnosis.submitted ? `Diagnosis recorded · ${score(payload.diagnosis.latest?.score)}/100` : 'Diagnosis pending'}</span>
      <span><FileSearch size={13} />{payload.attempt.scores.correctness == null ? 'No fix submitted' : `Fix correctness ${score(payload.attempt.scores.correctness)}%`}</span>
    </div>
    <div className="panel-tabs incident-tabs" role="tablist" aria-label="Incident workspace">{TABS.map(({ id, label, icon: Icon }) =>
      <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} onClick={() => select(id)}><Icon size={14} />{label}</button>)}</div>
    <div className="incident-tab-body" role="tabpanel">
      {tab === 'overview' ? <OverviewPanel incident={payload.incident} />
        : tab === 'observability' ? <ArtifactBrowser artifacts={payload.incident.artifacts} types={observabilityTypes} viewed={investigation.viewed} onOpen={open} empty="This incident has no logs, metrics or traces." />
          : tab === 'context' ? <ArtifactBrowser artifacts={payload.incident.artifacts} types={contextTypes} viewed={investigation.viewed} onOpen={open} empty="This incident has no system context artifacts." />
            : tab === 'debug' ? <DebugPanel payload={payload} onNeedDiagnosis={() => select('resolution')} onChanged={refresh} />
              : <ResolutionPanel payload={payload} onChanged={refresh} />}
    </div>
  </>;
}

function OverviewPanel({ incident }: { incident: IncidentOverview | SessionPayload['incident'] }) {
  const total = Object.values(incident.weights).reduce((sum, value) => sum + value, 0) || 1;
  return <div className="incident-overview">
    <section className="surface">
      <div className="surface-heading"><h2><Target size={16} /> Objective</h2></div>
      <p>{incident.objective}</p>
      <div className="incident-compare">
        <div><span className="eyebrow green">EXPECTED</span><p>{incident.expected_behavior}</p></div>
        <div><span className="eyebrow coral">OBSERVED</span><ul>{incident.observed_symptoms.map(item => <li key={item}>{item}</li>)}</ul></div>
      </div>
      <h3 className="incident-subheading"><AlertTriangle size={14} /> Impact</h3>
      <ul className="requirements">{incident.impact.map(item => <li key={item}>{item}</li>)}</ul>
    </section>
    <section className="surface">
      <div className="surface-heading"><h2><CalendarClock size={16} /> Timeline</h2></div>
      <ol className="incident-timeline">{incident.timeline.map((entry, index) => <li key={`${entry.at}:${index}`} className={`timeline-${entry.kind}`}>
        <span className="timeline-time mono">{clock(entry.at)}</span>
        <span className="timeline-marker" aria-hidden="true" />
        <div><span className={`timeline-kind ${entry.kind}`}>{timelineNames[entry.kind] ?? entry.kind}</span><strong>{entry.title}</strong>{entry.detail && <p>{entry.detail}</p>}</div>
      </li>)}</ol>
    </section>
    <section className="surface">
      <div className="surface-heading"><h2><FileSearch size={16} /> Evidence and scenarios</h2></div>
      <ul className="incident-evidence">{incident.artifacts.map(artifact => <li key={artifact.id}><strong>{artifact.title}</strong>{artifact.description && <span className="muted"> · {artifact.description}</span>}</li>)}</ul>
      <h3 className="incident-subheading"><Play size={14} /> Reproduction scenarios</h3>
      <ul className="requirements">{incident.scenarios.map(scenario => <li key={scenario.id}><strong>{scenario.name}</strong>{scenario.description ? ` — ${scenario.description}` : ''}</li>)}</ul>
    </section>
    <section className="surface">
      <div className="surface-heading"><h2><Gauge size={16} /> How the resolution is evaluated</h2></div>
      <div className="incident-weights">{dimensionOrder.filter(key => key in incident.weights).map(key => <div key={key}><span>{dimensionNames[key]}</span><strong>{Math.round(incident.weights[key] / total * 100)}%</strong></div>)}</div>
      <p className="muted">Fixing the immediate defect and preventing recurrence are reported separately.</p>
    </section>
  </div>;
}
