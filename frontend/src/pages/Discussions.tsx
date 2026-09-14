import { ArrowLeft, ArrowRight, ArrowUp, ChevronLeft, ChevronRight, MessageSquare, Plus, Search, Send, Trash2 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { api, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { dateLabel } from '../lib/constants';
import { Avatar, EmptyState, ErrorState, Loading, PageHeading, SignInCard } from '../components/ui';
import type { Discussion, Page, Problem } from '../types';

export default function Discussions() {
  const [params, setParams] = useSearchParams();
  const query = useQuery({ queryKey: ['discussions', params.toString()], queryFn: () => api<Page<Discussion>>(`/discussions?${params}`) });
  const problems = useQuery({ queryKey: ['problem-options'], queryFn: () => api<Page<Problem>>('/problems?limit=100') });
  function filter(key: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(key, value); else next.delete(key); if (key !== 'page') next.delete('page'); setParams(next, { replace: true }); }
  return <div className="page"><PageHeading eyebrow="DEBUGGING IS BETTER TOGETHER" title="Different perspectives. Better fixes." description="Ask a thoughtful question, share an insight, or work through a tricky idea." action={<Link className="button primary" to={`/discussions/new${params.get('problem_id') ? `?problem_id=${params.get('problem_id')}` : ''}`}><Plus size={16} />Start a discussion</Link>} /><div className="discussion-toolbar"><label className="search-input"><Search size={17} /><input aria-label="Search discussions" placeholder="Find a conversation…" value={params.get('q') || ''} onChange={event => filter('q', event.target.value)} /></label><select aria-label="Discussion case study" value={params.get('problem_id') || ''} onChange={event => filter('problem_id', event.target.value)}><option value="">All conversations</option>{problems.data?.items.map(problem => <option key={problem.id} value={problem.id}>{problem.title}</option>)}</select></div>
    {query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : !query.data.items.length ? <EmptyState icon={<MessageSquare size={29} />} title="Good conversations start with curiosity."><p>No discussions here yet. Be the first to share what you’re thinking.</p><Link className="button secondary" to="/discussions/new">Start the conversation <ArrowRight size={15} /></Link></EmptyState> : <><div className="discussion-list">{query.data.items.map(row => <article className="discussion-card" key={row.id}><div className="discussion-votes"><ArrowUp size={15} /><strong>{row.votes}</strong></div><div className="discussion-main">{row.problem_title && <Link className="discussion-problem" to={`/problems/${row.problem_slug}`}>{row.problem_title}</Link>}<Link to={`/discussions/${row.id}`} className="discussion-title">{row.title}</Link><p>{row.body.slice(0, 180)}{row.body.length > 180 ? '…' : ''}</p><div className="discussion-meta"><Avatar name={row.author} size="tiny" /><span>{row.author}</span><span>·</span><span>{dateLabel(row.created_at)}</span></div></div><Link className="reply-count" to={`/discussions/${row.id}`}><MessageSquare size={16} />{row.reply_count}<span>replies</span></Link></article>)}</div><div className="catalog-footer"><span>{query.data.total} conversations</span><div className="pagination"><button aria-label="Previous page" className="icon-button" disabled={query.data.page <= 1} onClick={() => filter('page', String(query.data.page - 1))}><ChevronLeft size={16} /></button><span>{query.data.page}</span><button aria-label="Next page" className="icon-button" disabled={query.data.page * query.data.limit >= query.data.total} onClick={() => filter('page', String(query.data.page + 1))}><ChevronRight size={16} /></button></div></div></>}
    <div className="community-guideline"><MessageSquare size={18} /><p>Make room for learning. Explain your reasoning, be kind, and keep complete solutions in the shared-fixes area.</p></div>
  </div>;
}

export function NewDiscussion() {
  const { user, loading } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const problems = useQuery({ queryKey: ['problem-options'], queryFn: () => api<Page<Problem>>('/problems?limit=100') });
  const mutation = useMutation({ mutationFn: (data: { title: string; body: string; problem_id: number | null }) => post<Discussion>('/discussions', data),
    onSuccess: row => { void client.invalidateQueries({ queryKey: ['discussions'] }); navigate(`/discussions/${row.id}`); }, onError: error => toast.error(error.message) });
  function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    mutation.mutate({ title: String(form.get('title')), body: String(form.get('body')), problem_id: form.get('problem') ? Number(form.get('problem')) : null });
  }
  return <div className="page narrow-page"><Link className="text-link" to="/discussions"><ArrowLeft size={15} />Back to discussions</Link><PageHeading eyebrow="THINK OUT LOUD" title="Start a conversation." description="A clear question is often the first step toward a great fix." />{loading ? <Loading /> : !user ? <SignInCard title="Join the conversation" /> : <form className="surface discussion-form" onSubmit={event => submit(event)}><label>Title<input name="title" placeholder="What are you thinking about?" minLength={5} maxLength={160} required /></label><label>Related case study<select name="problem" defaultValue={params.get('problem_id') || ''}><option value="">General discussion</option>{problems.data?.items.map(problem => <option value={problem.id} key={problem.id}>{problem.title}</option>)}</select></label><label>Your question or insight<textarea name="body" rows={10} minLength={10} maxLength={10000} required placeholder="Share the context, what you’ve tried, and where you’re stuck…" /></label><p className="muted">Help others understand your thinking. Save full solutions for the shared-fixes area.</p><div className="form-actions"><Link className="button secondary" to="/discussions">Cancel</Link><button className="button primary" disabled={mutation.isPending}><Send size={15} />{mutation.isPending ? 'Posting…' : 'Post discussion'}</button></div></form>}</div>;
}

export function DiscussionDetail() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [reply, setReply] = useState('');
  const query = useQuery({ queryKey: ['discussion', id, user?.id], queryFn: () => api<Discussion>(`/discussions/${id}`) });
  const mutation = useMutation({ mutationFn: () => post<Discussion>(`/discussions/${id}/replies`, { body: reply }),
    onSuccess: row => { setReply(''); client.setQueryData(['discussion', id, user?.id], row); void client.invalidateQueries({ queryKey: ['discussions'] }); }, onError: error => toast.error(error.message) });
  async function vote() {
    if (!user) { navigate(`/login?next=/discussions/${id}`); return; }
    try { const row = await post<Discussion>(`/discussions/${id}/vote`); client.setQueryData(['discussion', id, user.id], row); }
    catch (error) { toast.error((error as Error).message); }
  }
  async function remove(replyId?: string) {
    if (!window.confirm(replyId ? 'Delete your reply?' : 'Delete your discussion and its replies?')) return;
    try { await api(replyId ? `/replies/${replyId}` : `/discussions/${id}`, { method: 'DELETE' });
      if (replyId) await query.refetch(); else { await client.invalidateQueries({ queryKey: ['discussions'] }); navigate('/discussions'); }
    } catch (error) { toast.error((error as Error).message); }
  }
  if (query.isPending) return <Loading />;
  if (query.isError) return <div className="page"><ErrorState error={query.error} /></div>;
  const row = query.data;
  return <div className="page narrow-page"><Link className="text-link" to="/discussions"><ArrowLeft size={15} />All discussions</Link><article className="surface discussion-detail"><div className="discussion-meta"><Avatar name={row.author} /><div><strong>{row.author}</strong><span>{dateLabel(row.created_at)}</span></div>{row.author_id === user?.id && <button className="icon-button push-right" aria-label="Delete discussion" onClick={() => void remove()}><Trash2 size={16} /></button>}</div>{row.problem_title && <Link to={`/problems/${row.problem_slug}`} className="discussion-problem">{row.problem_title}</Link>}<h1>{row.title}</h1><p className="discussion-body">{row.body}</p><div className="discussion-detail-bottom"><button className={`button secondary small ${row.voted ? 'voted' : ''}`} aria-pressed={row.voted} onClick={() => void vote()}><ArrowUp size={15} />{row.votes} {row.votes === 1 ? 'upvote' : 'upvotes'}</button><span><MessageSquare size={14} />{row.reply_count} replies</span></div></article><h2 className="replies-heading">The conversation <span>{row.reply_count}</span></h2>{row.replies.map(item => <article className="surface reply-card" key={item.id}><div className="discussion-meta"><Avatar name={item.author} size="small" /><strong>{item.author}</strong><span>·</span><span>{dateLabel(item.created_at)}</span>{item.author_id === user?.id && <button className="icon-button push-right" aria-label="Delete reply" onClick={() => void remove(item.id)}><Trash2 size={14} /></button>}</div><p className="discussion-body">{item.body}</p></article>)}{user ? <form className="surface reply-form" onSubmit={event => { event.preventDefault(); mutation.mutate(); }}><label htmlFor="reply-body">Add your perspective</label><textarea id="reply-body" minLength={2} maxLength={5000} rows={4} value={reply} onChange={event => setReply(event.target.value)} required placeholder="A helpful observation, a different approach, a good question…" /><div className="form-actions"><button className="button primary" disabled={mutation.isPending}><Send size={14} />{mutation.isPending ? 'Posting…' : 'Post reply'}</button></div></form> : <SignInCard title="Have a thought to add?" />}</div>;
}

