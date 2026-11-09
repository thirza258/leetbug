import { ArrowRight, LoaderCircle, MailCheck } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../../lib/auth';
import { EmptyState, Loading, SignInCard } from '../../components/ui';
import { acceptInvitation } from './api';
import './assessments.css';

export default function InvitationAcceptPage() {
  const { token = '' } = useParams();
  const { user, loading } = useAuth();
  const accept = useMutation({ mutationFn: () => acceptInvitation(token) });
  if (loading) return <Loading />;
  if (!user) return <div className="page"><SignInCard title="Sign in to accept your invitation" /></div>;
  return <div className="page narrow-page"><EmptyState icon={<MailCheck size={28} />} title="You're invited to an assessment">
    {accept.isSuccess ? <><p>Invitation accepted for <strong>{accept.data.assessment.title}</strong>.</p><Link className="button primary" to={`/assessments/${accept.data.assessment.slug}`}>Review the rules <ArrowRight size={15} /></Link></>
      : <><p>Accepting links this invitation to <strong>{user.email}</strong>. It must match the address the organizer invited.</p>
        {accept.isError && <p className="inline-error">{accept.error.message}</p>}
        <button className="button primary" disabled={accept.isPending} onClick={() => accept.mutate()}>{accept.isPending && <LoaderCircle size={15} className="spin" />}Accept invitation</button></>}
  </EmptyState></div>;
}
