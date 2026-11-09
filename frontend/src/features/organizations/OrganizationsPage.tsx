import { ArrowRight, Building2, LoaderCircle, Plus } from 'lucide-react';
import { useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { useAuth } from '../../lib/auth';
import { EmptyState, ErrorState, Loading, PageHeading, SignInCard } from '../../components/ui';
import { createOrganization, listOrganizations } from './api';
import './organizations.css';

export default function OrganizationsPage() {
  const { user, loading } = useAuth();
  const list = useQuery({ queryKey: ['organizations', user?.id], queryFn: listOrganizations, enabled: !!user });
  if (loading) return <Loading />;
  if (!user) return <div className="page"><SignInCard title="Assess candidates with your team" /></div>;
  return <div className="page">
    <PageHeading eyebrow="COMPANY ACCOUNTS" title="Organizations" description="Run private assessment packs with your team: invite candidates, review reports, compare results and export them. Reports support hiring decisions; they never make them." />
    {list.isPending ? <Loading label="Loading organizations…" /> : list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} />
      : !list.data.items.length ? <EmptyState icon={<Building2 size={28} />} title="No organizations yet"><p>Create one below, or ask an owner to add your account.</p></EmptyState>
      : <div className="org-grid">{list.data.items.map(org => <article key={org.id} className="surface org-card">
        <div className="row-actions"><span className={`small-tag org-role ${org.role}`}>{org.role}</span></div>
        <h2><Link to={`/organizations/${org.slug}`}>{org.name}</Link></h2>
        <dl><div><dt>Members</dt><dd>{org.counts.members}</dd></div><div><dt>Assessments</dt><dd>{org.counts.assessments}</dd></div><div><dt>Reports</dt><dd>{org.counts.finalized_sessions}</dd></div></dl>
        <Link className="button secondary small" to={`/organizations/${org.slug}`}>Open <ArrowRight size={13} /></Link>
      </article>)}</div>}
    <CreateOrganization />
  </div>;
}

function CreateOrganization() {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const create = useMutation({ mutationFn: () => createOrganization(name.trim(), slug.trim() || undefined),
    onSuccess: org => { toast.success(`${org.name} created. You are its owner.`); void client.invalidateQueries({ queryKey: ['organizations'] }); navigate(`/organizations/${org.slug}`); },
    onError: error => toast.error(error.message) });
  function submit(event: FormEvent) { event.preventDefault(); create.mutate(); }
  return <section className="surface" aria-labelledby="create-organization">
    <div className="surface-heading"><h2 id="create-organization">Create an organization</h2><Building2 size={17} /></div>
    <form className="org-create" onSubmit={submit}>
      <label>Name<input required minLength={2} maxLength={150} value={name} onChange={event => setName(event.target.value)} placeholder="Acme Engineering" /></label>
      <label>Slug <small>Optional; lowercase letters, digits and hyphens.</small><input pattern="[a-z0-9][a-z0-9-]{2,99}" maxLength={100} value={slug} onChange={event => setSlug(event.target.value)} placeholder="acme-engineering" /></label>
      <button className="button primary" disabled={create.isPending || name.trim().length < 2}>{create.isPending ? <LoaderCircle size={14} className="spin" /> : <Plus size={14} />}Create</button>
    </form>
  </section>;
}
