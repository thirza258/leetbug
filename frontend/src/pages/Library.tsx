import { ArrowDownWideNarrow, ArrowRight, ArrowUpRight, Bookmark, Check, ChevronLeft, ChevronRight, Search, X } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { toast } from 'sonner';
import { api, post } from '../lib/api';
import { useAuth } from '../lib/auth';
import { categories, languageNames } from '../lib/constants';
import { Difficulty, EmptyState, ErrorState, Loading } from '../components/ui';
import type { Category, Language, Page, Problem } from '../types';

export default function Library() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const search = useRef<HTMLInputElement>(null);
  const query = useQuery({ queryKey: ['problems', params.toString(), user?.id],
    queryFn: () => api<Page<Problem> & { tags: string[] }>(`/problems?${params}`) });
  function filter(name: string, value: string) {
    // History updates synchronously even while React Router is rendering a transition.
    // Read the latest URL so rapid reset/select actions cannot resurrect an old filter.
    const next = new URLSearchParams(window.location.search);
    if (value) next.set(name, value); else next.delete(name);
    if (name !== 'page') next.delete('page');
    setParams(next, { replace: true });
  }
  useEffect(() => {
    const key = (event: KeyboardEvent) => {
      if (event.key === '/' && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLTextAreaElement)) {
        event.preventDefault(); search.current?.focus();
      }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, []);
  async function toggleBookmark(problem: Problem) {
    if (!user) { navigate('/login'); return; }
    try {
      await post(`/problems/${problem.slug}/bookmark`);
      await client.invalidateQueries({ queryKey: ['problems'] });
    } catch (error) { toast.error((error as Error).message); }
  }
  return <div className="page library-page">
    <div className="library-heading"><div><h1>Problem library</h1><p>Practice debugging real code. Choose a case, make a fix, and test it.</p></div>
      <div className="page-actions"><Link className="button primary" to={`/problems/${query.data?.items.find(problem => problem.status !== 'solved')?.slug || 'missing-last-item'}`}>{user ? 'Continue debugging' : 'Start a case'}<ArrowRight size={16} /></Link><Link className="button secondary" to={user ? '/submissions' : '/register'}>{user ? 'View submissions' : 'Create account'}</Link></div>
    </div>
    <div className="category-grid">{(Object.entries(categories) as [Category, typeof categories[Category]][]).map(([key, category]) => {
      const Icon = category.icon;
      return <button key={key} className={`category-card ${category.color} ${params.get('category') === key ? 'selected' : ''}`} onClick={() => filter('category', params.get('category') === key ? '' : key)} aria-pressed={params.get('category') === key}>
        <span className="category-icon"><Icon size={20} /></span><ArrowUpRight size={17} className="category-arrow" /><strong>{category.name}</strong><span>{category.description}</span>
      </button>;
    })}</div>
    <section aria-labelledby="catalog-heading" className="catalog-section"><div className="section-heading"><div className="tab-links"><button id="catalog-heading" className={!params.get('bookmarked') ? 'active' : ''} onClick={() => filter('bookmarked', '')}>All case studies <span>{query.data?.total ?? '—'}</span></button><button className={params.get('bookmarked') ? 'active' : ''} onClick={() => filter('bookmarked', 'true')}><Bookmark size={14} /> Saved for later</button></div><Link to="/guide" className="text-link">How it works <ArrowUpRight size={14} /></Link></div>
      <div className="filter-bar"><label className="search-input"><Search size={17} /><input ref={search} aria-label="Search case studies" placeholder="Search bugs, topics, or keywords…" value={params.get('q') || ''} onChange={event => filter('q', event.target.value)} /><kbd>/</kbd></label><select aria-label="Language filter" value={params.get('language') || ''} onChange={event => filter('language', event.target.value)}><option value="">All languages</option>{Object.entries(languageNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select aria-label="Difficulty filter" value={params.get('difficulty') || ''} onChange={event => filter('difficulty', event.target.value)}><option value="">All difficulties</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select><select aria-label="Progress filter" value={params.get('status') || ''} onChange={event => filter('status', event.target.value)}><option value="">Any status</option><option value="todo">To do</option><option value="attempted">Attempted</option><option value="solved">Solved</option></select><label className="sort-select"><ArrowDownWideNarrow size={16} /><select aria-label="Sort case studies" value={params.get('sort') || 'recommended'} onChange={event => filter('sort', event.target.value)}><option value="recommended">Recommended</option><option value="difficulty">Difficulty</option><option value="title">Title</option></select></label></div>
      {params.size > 0 && <div className="active-filters">{['category', 'tag', 'q', 'language', 'difficulty', 'status'].filter(key => params.has(key)).map(key => <button className="filter-chip" key={key} onClick={() => filter(key, '')}>{key === 'category' ? categories[params.get(key) as Category]?.short : params.get(key)}<X size={12} /></button>)}<button className="text-link" onClick={() => setParams({})}>Reset filters</button></div>}
      {query.isPending ? <Loading label="Finding your next bug…" /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : !query.data.items.length ? <EmptyState icon={<Search size={28} />} title={params.has('bookmarked') ? 'Your reading list starts here' : 'No bugs match these filters'}><p>{params.has('bookmarked') ? 'Bookmark a case study to come back to it later.' : 'Try a different keyword or clear a filter.'}</p><button className="button secondary" onClick={() => setParams({})}>Explore all cases</button></EmptyState> : <div className="problem-table-wrap"><table className="problem-table"><thead><tr><th className="state-cell" aria-label="Status" /><th>CASE STUDY</th><th>DIFFICULTY</th><th>CATEGORY</th><th>LANGUAGE</th><th className="acceptance-column">ACCEPTANCE</th><th aria-label="Actions" /></tr></thead><tbody>{query.data.items.map(problem => <tr key={problem.id}>
        <td className="state-cell">{problem.status === 'solved' ? <Check size={17} className="green" aria-label="Solved" /> : <span className={`problem-state ${problem.status}`} title={problem.status === 'attempted' ? 'Attempted' : 'To do'} />}</td>
        <td><Link className="problem-title" to={`/problems/${problem.slug}`}><span className="problem-number">{String(problem.id).padStart(2, '0')}.</span>{problem.title}</Link><div className="problem-tags">{problem.tags.slice(0, 2).map(tag => <button key={tag} onClick={() => filter('tag', tag)}>{tag}</button>)}<span>·</span><span>{problem.estimated_minutes} min</span></div></td>
        <td><Difficulty value={problem.difficulty} /></td><td><span className={`category-pill ${categories[problem.category].color}`}>{categories[problem.category].short}</span></td><td><div className="language-cell"><span className={`language-dot ${problem.languages[0]}`} />{languageNames[problem.languages[0] as Language]}{problem.languages.length > 1 && <span className="extra-languages" title={problem.languages.slice(1).map(l => languageNames[l]).join(', ')}>+{problem.languages.length - 1}</span>}</div></td>
        <td className="acceptance-column"><span className="mono muted">{problem.acceptance_rate == null ? '—' : `${problem.acceptance_rate}%`}</span></td><td><div className="row-actions"><Link className="button secondary small" to={`/problems/${problem.slug}`}>Debug <ArrowRight size={13} /></Link><button className={`icon-button bookmark-button ${problem.bookmarked ? 'saved' : ''}`} aria-label={`${problem.bookmarked ? 'Unsave' : 'Save'} ${problem.title}`} onClick={() => void toggleBookmark(problem)}><Bookmark size={16} fill={problem.bookmarked ? 'currentColor' : 'none'} /></button></div></td>
      </tr>)}</tbody></table></div>}
      <div className="catalog-footer"><span>{query.data?.total ?? 0} case studies</span><div className="pagination"><button className="icon-button" aria-label="Previous page" disabled={Number(params.get('page') || 1) <= 1} onClick={() => filter('page', String(Number(params.get('page') || 1) - 1))}><ChevronLeft size={16} /></button><span>{params.get('page') || 1}</span><button className="icon-button" aria-label="Next page" disabled={!query.data || query.data.page * query.data.limit >= query.data.total} onClick={() => filter('page', String(Number(params.get('page') || 1) + 1))}><ChevronRight size={16} /></button></div></div>
    </section>
    <div className="catalog-actions"><div><strong>Need help getting started?</strong><p>Learn the workspace or work through a question with the community.</p></div><div className="page-actions"><Link className="button secondary" to="/guide">Read the guide</Link><Link className="button secondary" to="/discussions/new">Ask a question <ArrowRight size={15} /></Link></div></div>
  </div>;
}
