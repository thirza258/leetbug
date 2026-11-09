import { CheckCircle2, CircleAlert, FlaskConical, LoaderCircle, Upload } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ErrorState, Loading } from '../../components/ui';
import { adminAction, adminCreate, adminIncidents } from './api';

/** Administrator authoring (PI-001): import a definition as a draft, validate reproduction, publish. */
export default function IncidentAdmin() {
  const client = useQueryClient();
  const [definition, setDefinition] = useState('');
  const list = useQuery({ queryKey: ['admin-incidents'], queryFn: adminIncidents,
    refetchInterval: query => query.state.data?.items.some(item => item.validation.status === 'queued' || item.validation.status === 'running') ? 2000 : false });
  const refresh = () => { void client.invalidateQueries({ queryKey: ['admin-incidents'] }); void client.invalidateQueries({ queryKey: ['incidents'] }); };
  const act = useMutation({ mutationFn: ({ slug, action }: { slug: string; action: 'validate' | 'publish' | 'unpublish' }) => adminAction(slug, action),
    onSuccess: refresh, onError: error => toast.error(error.message) });
  const create = useMutation({
    mutationFn: () => { let parsed: unknown; try { parsed = JSON.parse(definition); } catch { throw new Error('The definition must be valid JSON.'); } return adminCreate(parsed); },
    onSuccess: row => { toast.success(`Draft ${row.slug} created. Validate it before publishing.`); setDefinition(''); refresh(); },
    onError: error => toast.error(error.message),
  });
  return <section className="surface incident-admin">
    <div className="surface-heading"><h2><FlaskConical size={16} /> Incident administration</h2><span className="small-tag">ADMIN</span></div>
    <p className="muted">Drafts stay hidden until a validation run shows the defect reproduces and the reference fix passes every test.</p>
    {list.isPending ? <Loading label="Loading incidents…" /> : list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} />
      : <div className="incident-table-wrap"><table>
        <thead><tr><th>INCIDENT</th><th>STATUS</th><th>VALIDATION</th><th>SESSIONS</th><th aria-label="Actions" /></tr></thead>
        <tbody>{list.data.items.map(item => {
          const state = item.validation.status;
          const busy = state === 'queued' || state === 'running';
          return <tr key={item.slug}>
            <td><strong>{item.title}</strong><small className="muted mono"> {item.slug} · v{item.version}</small></td>
            <td>{item.status}</td>
            <td className="incident-validation">{busy ? <><LoaderCircle size={13} className="spin" />{state}</>
              : item.validation.current ? <><CheckCircle2 size={13} className="green" />passed</>
                : state ? <><CircleAlert size={13} className="coral" />{state === 'passed' ? 'outdated' : state}</> : <span className="muted">not run</span>}
              {item.validation.error && <small className="muted"> {item.validation.error}</small>}</td>
            <td>{item.sessions}</td>
            <td><div className="row-actions">
              <button className="button secondary small" disabled={busy || act.isPending} onClick={() => act.mutate({ slug: item.slug, action: 'validate' })}>Validate</button>
              {item.status === 'published'
                ? <button className="button secondary small" disabled={act.isPending} onClick={() => act.mutate({ slug: item.slug, action: 'unpublish' })}>Unpublish</button>
                : <button className="button primary small" disabled={!item.validation.current || act.isPending} onClick={() => act.mutate({ slug: item.slug, action: 'publish' })}>Publish</button>}
            </div></td>
          </tr>;
        })}</tbody>
      </table></div>}
    <form className="resolution-form incident-import" onSubmit={event => { event.preventDefault(); create.mutate(); }}>
      <label>Import an incident definition (JSON, same format as the bundled catalog)
        <textarea className="mono" rows={6} value={definition} onChange={event => setDefinition(event.target.value)} placeholder='{"slug": "...", "title": "...", "problem": {...}, "artifacts": [...]}' /></label>
      <div className="resolution-actions"><span className="muted">Definitions are checked for structure and for anything that looks like a real credential, email or public address.</span>
        <button className="button primary small" disabled={!definition.trim() || create.isPending}>{create.isPending ? <LoaderCircle size={13} className="spin" /> : <Upload size={13} />}Create draft</button></div>
    </form>
  </section>;
}
