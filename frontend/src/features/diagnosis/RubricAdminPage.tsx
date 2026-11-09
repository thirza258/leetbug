import { ChevronLeft, ChevronRight, RotateCcw, Save, ScrollText, Search } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from '../../lib/api';
import { useAuth } from '../../lib/auth';
import { EmptyState, ErrorState, Loading, PageHeading } from '../../components/ui';
import type { Page } from '../../types';
import type { Rubric, RubricDetail, RubricSummary } from './types';
import './diagnosis.css';

const sourceLabels = { derived: 'Derived', authored: 'Authored', admin: 'Admin override' } as const;

// Route: /admin/rubrics (DR-008, DR-009). Changes are versioned and written to the audit log by the API.
export default function RubricAdminPage() {
  const { user, loading } = useAuth();
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: ['admin-rubrics', q, page],
    queryFn: () => api<Page<RubricSummary>>(`/admin/rubrics?q=${encodeURIComponent(q)}&page=${page}`), enabled: !!user?.is_admin });
  if (loading) return <Loading />;
  if (!user?.is_admin) return <div className="page"><EmptyState title="Admin access required"><p>This page is restricted to administrators.</p><Link className="button primary" to="/">Back to library</Link></EmptyState></div>;
  return <div className="page"><PageHeading eyebrow="ADMIN" title="Diagnosis rubrics" description="Review and correct the concepts each diagnosis is scored against. Every change is versioned and recorded in the audit log." />
    <div className="dx-admin">
      <section className="surface dx-admin-list" aria-label="Problems">
        <label className="search-input"><Search size={16} aria-hidden /><input aria-label="Search problems" placeholder="Search by title or slug…" value={q} onChange={event => { setQ(event.target.value); setPage(1); }} /></label>
        {list.isPending ? <Loading label="Loading problems…" /> : list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} /> : <>
          <ul className="dx-list">{list.data.items.map(row => <li key={row.slug}>
            <button type="button" aria-current={selected === row.slug} onClick={() => setSelected(row.slug)}>
              <strong>{row.title}</strong><span>{row.slug} · {sourceLabels[row.rubric_source]} v{row.rubric_version} · diagnosis {row.diagnosis_mode}</span>
            </button></li>)}</ul>
          <div className="dx-pager"><span>{list.data.total} problems</span><div>
            <button className="icon-button" aria-label="Previous page" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button>
            <button className="icon-button" aria-label="Next page" disabled={page * list.data.limit >= list.data.total} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button>
          </div></div>
        </>}
      </section>
      <section className="surface">{selected ? <RubricEditor key={selected} slug={selected} />
        : <EmptyState icon={<ScrollText size={28} />} title="Choose a problem"><p>Select a problem to review its effective rubric.</p></EmptyState>}</section>
    </div>
  </div>;
}

function RubricEditor({ slug }: { slug: string }) {
  const detail = useQuery({ queryKey: ['admin-rubric', slug], queryFn: () => api<RubricDetail>(`/admin/problems/${slug}/rubric`) });
  if (detail.isPending) return <Loading label="Loading rubric…" />;
  if (detail.isError) return <ErrorState error={detail.error} retry={() => void detail.refetch()} />;
  return <RubricForm key={`${detail.data.rubric_version}:${detail.data.diagnosis_mode}`} detail={detail.data} />;
}

function editable(rubric: Rubric) {
  const copy: Record<string, unknown> = { ...rubric };
  delete copy.version; delete copy.source; delete copy.format;
  return JSON.stringify(copy, null, 2);
}

function RubricForm({ detail }: { detail: RubricDetail }) {
  const client = useQueryClient();
  const [text, setText] = useState(() => editable(detail.effective));
  const [error, setError] = useState<string | null>(null);
  const refresh = async (data: RubricDetail) => {
    client.setQueryData(['admin-rubric', detail.slug], data);
    await client.invalidateQueries({ queryKey: ['admin-rubrics'] });
  };
  const save = useMutation({
    mutationFn: () => {
      let parsed: unknown;
      try { parsed = JSON.parse(text); } catch (cause) { throw new Error(`The rubric is not valid JSON: ${(cause as Error).message}`, { cause }); }
      return api<RubricDetail>(`/admin/problems/${detail.slug}/rubric`, { method: 'PUT', body: JSON.stringify(parsed) });
    },
    onSuccess: async data => { setError(null); toast.success(`Rubric saved as version ${data.rubric_version}.`); await refresh(data); },
    onError: cause => setError(cause.message),
  });
  const revert = useMutation({
    mutationFn: () => api<RubricDetail>(`/admin/problems/${detail.slug}/rubric`, { method: 'DELETE' }),
    onSuccess: async data => { toast.success(`Reverted to the ${sourceLabels[data.source].toLowerCase()} rubric.`); await refresh(data); },
    onError: cause => toast.error(cause.message),
  });
  const mode = useMutation({
    mutationFn: (value: string) => api(`/admin/problems/${detail.slug}/diagnosis-mode`, { method: 'PATCH', body: JSON.stringify({ mode: value }) }),
    onSuccess: async () => { toast.success('Diagnosis requirement updated.'); await client.invalidateQueries({ queryKey: ['admin-rubric', detail.slug] }); await client.invalidateQueries({ queryKey: ['admin-rubrics'] }); },
    onError: cause => toast.error(cause.message),
  });
  return <div className="dx-panel">
    <div className="surface-heading"><h2>{detail.title}</h2><span className="dx-pill neutral">{sourceLabels[detail.source]} · v{detail.rubric_version}</span></div>
    <label className="dx-field">Diagnosis requirement
      <select value={detail.diagnosis_mode} disabled={mode.isPending} onChange={event => mode.mutate(event.target.value)}>
        <option value="optional">Optional</option><option value="required">Required before Submit fix</option><option value="off">Off</option>
      </select>
      <small>Assessments and incidents can require a diagnosis regardless of this setting.</small>
    </label>
    <label className="dx-field">Effective rubric (JSON)
      <textarea className="dx-json" spellCheck={false} value={text} onChange={event => setText(event.target.value)} />
      <small>Concept groups are lists of synonyms; a group matches when any phrase appears. Categories use taxonomy ids: {detail.categories.map(category => category.id).join(', ')}.</small>
    </label>
    {error && <p className="inline-error" role="alert">{error}</p>}
    <div className="dx-admin-actions">
      <button className="button primary small" disabled={save.isPending} onClick={() => save.mutate()}><Save size={13} aria-hidden />Save override</button>
      <button className="button secondary small" disabled={revert.isPending || detail.source !== 'admin'} onClick={() => revert.mutate()}><RotateCcw size={13} aria-hidden />Revert override</button>
      <button className="button ghost small" onClick={() => { setText(editable(detail.derived)); setError(null); }}>Load derived rubric</button>
    </div>
  </div>;
}
