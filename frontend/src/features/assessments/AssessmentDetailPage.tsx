import { ArrowLeft, ArrowRight, Check, ClipboardCheck, LoaderCircle } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import { languageNames } from '../../lib/constants';
import { ErrorState, Loading, SignInCard } from '../../components/ui';
import { getAssessment, startAssessment } from './api';
import { typeNames, when } from './format';
import { PolicyBadges } from './shared';
import './assessments.css';

export default function AssessmentDetailPage() {
  const { slug = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['assessment', slug, user?.id], queryFn: () => getAssessment(slug) });
  const start = useMutation({ mutationFn: () => startAssessment(slug), onSuccess: session => {
    void client.invalidateQueries({ queryKey: ['assessments'] });
    void client.invalidateQueries({ queryKey: ['assessment-history'] });
    navigate(`/assessment-sessions/${session.id}`);
  }, onError: error => toast.error(error.message) });
  if (query.isPending) return <Loading label="Opening assessment…" />;
  if (query.isError) return <div className="page"><ErrorState error={query.error} retry={() => void query.refetch()} /></div>;
  const item = query.data;
  return <div className="page narrow-page">
    <Link to="/assessments" className="text-link"><ArrowLeft size={15} /> All assessments</Link>
    <div className="asm-detail-head"><span className="small-tag">{typeNames[item.assessment_type]}</span><h1>{item.title}</h1><p className="muted">{item.description}</p><PolicyBadges policy={item.assistance_policy} duration={item.duration_seconds} /></div>
    <div className="asm-detail-grid">
      <section className="surface"><div className="surface-heading"><h2>Before you start</h2><ClipboardCheck size={17} /></div>
        <ul className="asm-rules">{item.rules.map(rule => <li key={rule}><Check size={14} />{rule}</li>)}</ul></section>
      <section className="surface"><div className="surface-heading"><h2>At a glance</h2></div>
        <dl className="asm-facts stacked"><div><dt>Challenges</dt><dd>{item.challenge_count} ({item.difficulty_mix.easy} easy, {item.difficulty_mix.medium} medium, {item.difficulty_mix.hard} hard)</dd></div>
          <div><dt>Languages</dt><dd>{item.languages.map(language => languageNames[language] ?? language).join(', ')}</dd></div>
          <div><dt>Diagnosis</dt><dd>{item.diagnosis_required ? 'Required before each fix' : 'Optional, scored when given'}</dd></div>
          <div><dt>Fix explanation</dt><dd>{item.explanation_required ? 'Required' : 'Optional'}</dd></div>
          <div><dt>Submissions</dt><dd>{item.max_attempts ? `${item.max_attempts} per challenge` : 'Unlimited'}</dd></div>
          <div><dt>Sessions</dt><dd>{item.max_sessions ? `${item.sessions_used} of ${item.max_sessions} used` : `${item.sessions_used} used`}</dd></div>
          <div><dt>Results</dt><dd>{item.feedback === 'delayed' ? 'Released after review' : 'Immediately after you finish'}</dd></div>
          {item.available_until && <div><dt>Open until</dt><dd>{when(item.available_until)}</dd></div>}</dl>
        {!user ? <SignInCard title="Sign in to take this assessment" /> : item.active_session_id
          ? <Link className="button primary full" to={`/assessment-sessions/${item.active_session_id}`}>Resume session <ArrowRight size={15} /></Link>
          : item.can_start ? <button className="button primary full" disabled={start.isPending} onClick={() => start.mutate()}>{start.isPending ? <LoaderCircle size={15} className="spin" /> : null}Start the assessment <ArrowRight size={15} /></button>
            : <p className="inline-error">{item.start_blocker}</p>}
        {item.my_session && !item.active_session_id && <Link className="text-link asm-last-report" to={`/assessment-sessions/${item.my_session.id}/report`}>View your last report <ArrowRight size={13} /></Link>}
      </section>
    </div>
  </div>;
}
