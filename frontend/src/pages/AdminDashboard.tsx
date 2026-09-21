import { Check, ChevronLeft, ChevronRight, Eye, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { getAdminSubmissions, getAdminSubmission, reviewSubmission } from '../lib/api';
import { useAuth } from '../lib/auth';
import { EmptyState, ErrorState, Loading, PageHeading, Difficulty } from '../components/ui';
import { categories, languageNames, dateLabel } from '../lib/constants';
import type { Language, ProblemSubmission } from '../types';
import Modal from '../components/Modal';

export default function AdminDashboard() {
  const { user } = useAuth();
  const client = useQueryClient();
  const [statusFilter, setStatusFilter] = useState('pending');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewing, setReviewing] = useState(false);

  const list = useQuery({
    queryKey: ['admin-submissions', statusFilter, page],
    queryFn: () => getAdminSubmissions(statusFilter, page),
  });

  const detail = useQuery({
    queryKey: ['admin-submission', selected],
    queryFn: () => getAdminSubmission(selected!),
    enabled: !!selected,
  });

  if (!user?.is_admin) {
    return <div className="page"><EmptyState title="Admin access required"><p>This page is restricted to administrators.</p><Link className="button primary" to="/">Back to library</Link></EmptyState></div>;
  }

  async function handleReview(action: 'approved' | 'rejected') {
    if (!selected) return;
    setReviewing(true);
    try {
      await reviewSubmission(selected, action, reviewNotes);
      toast.success(`Submission ${action}.`);
      setSelected(null);
      setReviewNotes('');
      await client.invalidateQueries({ queryKey: ['admin-submissions'] });
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setReviewing(false);
    }
  }

  const statusColor = (s: string) => s === 'approved' ? 'green' : s === 'rejected' ? 'coral' : 'amber';

  return (
    <div className="page">
      <PageHeading eyebrow="ADMIN" title="Problem submissions" description="Review community-submitted debugging problems. Approve or reject them with feedback." />

      <div className="discussion-toolbar">
        <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {list.isPending ? <Loading label="Loading submissions…" /> :
       list.isError ? <ErrorState error={list.error} retry={() => void list.refetch()} /> :
       !list.data.items.length ? <EmptyState icon={<ShieldCheck size={28} />} title="No submissions found"><p>No problem submissions match the current filter.</p></EmptyState> :
      <>
        <div className="problem-table-wrap">
          <table className="problem-table">
            <thead><tr>
              <th>TITLE</th>
              <th>AUTHOR</th>
              <th>CATEGORY</th>
              <th>DIFFICULTY</th>
              <th>STATUS</th>
              <th>DATE</th>
              <th aria-label="Actions" />
            </tr></thead>
            <tbody>
              {list.data.items.map((sub: ProblemSubmission) => (
                <tr key={sub.id}>
                  <td><strong style={{ fontSize: 12, fontWeight: 500 }}>{sub.title}</strong></td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>{sub.author_username || '—'}</td>
                  <td><span className={`category-pill ${categories[sub.category]?.color || ''}`}>{categories[sub.category]?.short || sub.category}</span></td>
                  <td><Difficulty value={sub.difficulty} /></td>
                  <td><span className={`status-badge ${statusColor(sub.status)}`} style={{ textTransform: 'capitalize' }}>{sub.status}</span></td>
                  <td style={{ fontSize: 12, color: 'var(--muted)' }}>{dateLabel(sub.created_at)}</td>
                  <td><button className="button secondary small" onClick={() => { setSelected(sub.id); setReviewNotes(sub.admin_notes || ''); }}><Eye size={13} /> Review</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="catalog-footer">
          <span>{list.data.total} submissions</span>
          <div className="pagination">
            <button className="icon-button" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button>
            <span>{page}</span>
            <button className="icon-button" disabled={page * list.data.limit >= list.data.total} onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button>
          </div>
        </div>
      </>
      }

      {selected && detail.data && (
        <Modal label="Review submission" onDismiss={() => setSelected(null)}>
          <div style={{ padding: '0 4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 20 }}>{detail.data.title}</h2>
              <button className="icon-button" onClick={() => setSelected(null)}><X size={18} /></button>
            </div>

            <div style={{ display: 'flex', gap: 12, marginBottom: 18, flexWrap: 'wrap' }}>
              <span className={`category-pill ${categories[detail.data.category]?.color || ''}`}>{categories[detail.data.category]?.short || detail.data.category}</span>
              <Difficulty value={detail.data.difficulty} />
              <span className="muted" style={{ fontSize: 12 }}>{languageNames[detail.data.language as Language] || detail.data.language}</span>
              {detail.data.author_username && <span className="muted" style={{ fontSize: 12 }}>by {detail.data.author_username}</span>}
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Summary</strong>
              <p style={{ fontSize: 13, color: 'var(--muted)' }}>{detail.data.summary}</p>
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Description</strong>
              <div className="discussion-body" style={{ fontSize: 13 }}>{detail.data.description}</div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Buggy code</strong>
              <pre style={{ background: 'var(--panel-soft)', padding: 14, borderRadius: 7, border: '1px solid var(--line)', maxHeight: 250, overflow: 'auto' }}>{detail.data.buggy_code}</pre>
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Fixed code</strong>
              <pre style={{ background: 'var(--panel-soft)', padding: 14, borderRadius: 7, border: '1px solid var(--line)', maxHeight: 250, overflow: 'auto' }}>{detail.data.fixed_code}</pre>
            </div>

            {detail.data.hint && <div style={{ marginBottom: 16 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Hint</strong>
              <p style={{ fontSize: 13, color: 'var(--muted)' }}>{detail.data.hint}</p>
            </div>}

            <div style={{ marginBottom: 20 }}>
              <strong style={{ fontSize: 12, display: 'block', marginBottom: 6 }}>Test cases ({detail.data.test_cases.length})</strong>
              {detail.data.test_cases.map((tc, i) => (
                <div key={i} className="example-card" style={{ marginBottom: 8 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    <div><span className="muted" style={{ fontSize: 11 }}>Input</span><pre>{typeof tc.input === 'string' ? tc.input : JSON.stringify(tc.input)}</pre></div>
                    <div><span className="muted" style={{ fontSize: 11 }}>Expected</span><pre>{typeof tc.expected === 'string' ? tc.expected : JSON.stringify(tc.expected)}</pre></div>
                  </div>
                </div>
              ))}
            </div>

            {detail.data.status === 'pending' ? (
              <>
                <label style={{ marginBottom: 16 }}>Admin notes
                  <textarea value={reviewNotes} onChange={e => setReviewNotes(e.target.value)} rows={3}
                    placeholder="Optional feedback for the submitter…" />
                </label>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                  <button className="button secondary" disabled={reviewing}
                    onClick={() => void handleReview('rejected')}><X size={14} /> Reject</button>
                  <button className="button primary" disabled={reviewing}
                    onClick={() => void handleReview('approved')}><Check size={14} /> Approve</button>
                </div>
              </>
            ) : (
              <div className="inline-error" style={{ background: 'var(--panel-soft)' }}>
                <strong style={{ textTransform: 'capitalize' }}>{detail.data.status}</strong>
                {detail.data.admin_notes && <span> — {detail.data.admin_notes}</span>}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
}
