import { ArrowUpRight, Code2, Sparkles, Trophy } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { ms } from '../lib/constants';
import { Avatar, EmptyState, ErrorState, Loading, PageHeading } from '../components/ui';
import type { Page, Problem, Rank } from '../types';

export default function Leaderboard() {
  const [mode, setMode] = useState<'all' | 'ai'>('all');
  const [problemId, setProblemId] = useState('');
  const { user } = useAuth();
  const problems = useQuery({ queryKey: ['problem-options'], queryFn: () => api<Page<Problem>>('/problems?limit=100') });
  const query = useQuery({ queryKey: ['leaderboard', mode, problemId], queryFn: () => api<{ items: Rank[] }>(`/leaderboard?mode=${mode}${problemId ? `&problem_id=${problemId}` : ''}`) });
  return <div className="page"><PageHeading eyebrow="A LITTLE FRIENDLY COMPETITION" title="Leaderboard" description="Compare accepted fixes and prompt efficiency." action={<Link className="button primary" to="/">Solve a case <ArrowUpRight size={15} /></Link>} />
    <div className="section-heading leaderboard-filters"><div className="tab-links"><button className={mode === 'all' ? 'active' : ''} onClick={() => setMode('all')}><Code2 size={15} />All debuggers</button><button className={mode === 'ai' ? 'active' : ''} onClick={() => setMode('ai')}><Sparkles size={15} />Prompt efficiency</button></div><select aria-label="Leaderboard case study" value={problemId} onChange={event => setProblemId(event.target.value)}><option value="">All case studies</option>{problems.data?.items.map(problem => <option key={problem.id} value={problem.id}>{problem.title}</option>)}</select></div>
    {query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} /> : !query.data.items.length ? <EmptyState icon={<Trophy size={28} />} title="The first spot is waiting."><p>{mode === 'ai' ? 'Submit an accepted AI fix to join the prompt leaderboard.' : 'Solve a case study to put your name on the board.'}</p><Link className="button primary" to="/">Find your first fix <ArrowUpRight size={15} /></Link></EmptyState> : <div className="surface leaderboard-table"><table className="data-table"><thead><tr><th>RANK</th><th>DEBUGGER</th><th>CASES SOLVED</th>{mode === 'ai' && <th>AVG. PROMPT WORDS</th>}<th>AVG. RUNTIME</th></tr></thead><tbody>{query.data.items.map(row => <tr key={row.user_id} className={user?.id === row.user_id ? 'own-rank' : ''}><td><span className={`rank-number rank-${row.rank}`}>{row.rank <= 3 ? <Trophy size={18} /> : String(row.rank).padStart(2, '0')}</span></td><td><div className="rank-user"><Avatar name={row.username} /><strong>{row.username}</strong>{row.user_id === user?.id && <span className="small-tag">YOU</span>}</div></td><td><strong className="mono">{row.solved}</strong></td>{mode === 'ai' && <td className="mono purple">{row.prompt_words}</td>}<td className="mono muted">{ms(row.runtime_ms)}</td></tr>)}</tbody></table></div>}
    <p className="metric-footnote">{mode === 'ai' ? 'Ranked by distinct AI-solved cases, then average word count of each case’s shortest accepted prompt, then runtime. Word counts measure directives, not model tokens. View shared prompts after solving the corresponding case.' : 'Ranked by distinct cases solved, then average runtime of each case’s fastest accepted fix. Only full submissions that pass every test qualify.'}</p>
  </div>;
}

