import { ArrowUpRight, BookOpen, ChevronLeft, ChevronRight, Code2, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { dateLabel, languageNames, ms, pending } from '../lib/constants';
import { EmptyState, ErrorState, Loading, PageHeading, SignInCard, StatusBadge } from '../components/ui';
import type { Page, Submission } from '../types';

export default function HistoryPage() {
  const { user, loading } = useAuth();
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ['submissions', 'history', user?.id, page],
    queryFn: () => api<Page<Submission>>(`/submissions?page=${page}`), enabled: !!user,
    refetchInterval: query => query.state.data?.items.some(row => pending(row.status)) ? 1500 : false });
  return <div className="page"><PageHeading eyebrow="THE STORY OF YOUR FIXES" title="Every attempt teaches you something." description="Revisit your code, compare approaches, and pick up where you left off." />
    {loading ? <Loading /> : !user ? <SignInCard title="Keep a record of your thinking" /> : query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : !query.data.items.length ? <EmptyState icon={<BookOpen size={28} />} title="A clean slate, a curious mind."><p>Your runs and submissions will appear here.</p><Link className="button primary" to="/">Find your first bug <ArrowUpRight size={15} /></Link></EmptyState> : <><div className="surface history-table-wrap"><table className="data-table"><thead><tr><th>CASE STUDY</th><th>RESULT</th><th>APPROACH</th><th>RUNTIME</th><th>DATE</th><th /></tr></thead><tbody>{query.data.items.map(row => <tr key={row.id}><td><Link className="problem-title" to={`/problems/${row.problem_slug}?submission=${row.id}`}>{row.problem_title}</Link><small className="history-id">{row.id.slice(0, 8)} · {row.kind === 'run' ? 'Public run' : 'Full submission'}</small></td><td><StatusBadge status={row.status} /></td><td><span className="mode-label">{row.mode === 'ai' ? <Sparkles size={13} /> : <Code2 size={14} />}{languageNames[row.language]} · {row.mode === 'ai' ? 'AI assist' : 'Manual'}</span></td><td className="mono">{ms(row.runtime_ms)}</td><td className="muted">{dateLabel(row.created_at)}</td><td><Link className="icon-button" aria-label={`Open submission for ${row.problem_title}`} to={`/problems/${row.problem_slug}?submission=${row.id}`}><ArrowUpRight size={16} /></Link></td></tr>)}</tbody></table></div><div className="catalog-footer"><span>{query.data.total} attempts and counting.</span><div className="pagination"><button className="icon-button" disabled={page === 1} aria-label="Previous page" onClick={() => setPage(page - 1)}><ChevronLeft size={16} /></button><span>{page}</span><button className="icon-button" disabled={page * 20 >= query.data.total} aria-label="Next page" onClick={() => setPage(page + 1)}><ChevronRight size={16} /></button></div></div></>}
  </div>;
}

