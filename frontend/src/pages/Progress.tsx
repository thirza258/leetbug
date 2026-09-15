import { ArrowRight, Award, CheckCheck, Flame, Pencil, Sparkles, Target, TrendingUp } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { categories, ms } from '../lib/constants';
import { Avatar, ErrorState, Loading, PageHeading, SignInCard } from '../components/ui';
import type { PersonalStats, PlatformStats, User } from '../types';

export default function Progress() {
  const { user, loading } = useAuth();
  const stats = useQuery({ queryKey: ['stats', user?.id], queryFn: () => api<PersonalStats>('/analytics/me'), enabled: !!user });
  const platform = useQuery({ queryKey: ['platform'], queryFn: () => api<PlatformStats>('/analytics/platform') });
  if (loading) return <Loading />;
  if (!user) return <div className="page"><SignInCard /></div>;
  return <div className="page"><PageHeading eyebrow="EVERY FIX COUNTS" title="My progress" description="Track solved cases, activity, and the skills you are building." action={<Link className="button primary" to="/">Find your next bug <ArrowRight size={15} /></Link>} />
    <Profile user={user} />
    {stats.isPending ? <Loading /> : stats.isError ? <ErrorState error={stats.error} retry={() => void stats.refetch()} /> : <>
      <div className="stat-grid">{[
        { label: 'Case studies solved', value: `${stats.data.solved}`, detail: `of ${stats.data.total_problems} challenges`, icon: CheckCheck, color: 'purple' },
        { label: 'Completion rate', value: `${stats.data.completion_rate}%`, detail: `${stats.data.attempts} evaluated submissions`, icon: Target, color: 'green' },
        { label: 'Current streak', value: `${stats.data.streak}`, detail: `day${stats.data.streak !== 1 ? 's' : ''} of showing up`, icon: Flame, color: 'amber' },
        { label: 'AI-assisted attempts', value: `${stats.data.ai_attempts}`, detail: `${stats.data.manual_attempts} hands-on attempts`, icon: Sparkles, color: 'blue' },
      ].map(({ label, value, detail, icon: Icon, color }) => <div className="stat-card" key={label}><span className={`stat-icon ${color}`}><Icon size={19} /></span><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>)}</div>
      <div className="progress-columns"><section className="surface"><div className="surface-heading"><h2>Your debugging range</h2><TrendingUp size={17} /></div><p className="muted">Build confidence across debugging and system design.</p><div className="category-progress">{stats.data.categories.map(item => { const category = categories[item.category]; const Icon = category.icon; return <div key={item.category}><div><span className={category.color}><Icon size={16} /></span><strong>{category.name}</strong><span>{item.solved} <span className="muted">/ {item.total}</span></span></div><div className="progress-track"><span className={category.color} style={{ width: `${item.total ? item.solved / item.total * 100 : 0}%` }} /></div></div>; })}</div></section>
      <section className="surface"><div className="surface-heading"><h2>A little practice adds up</h2><span className="small-tag">LAST 13 WEEKS</span></div><p className="muted">Every square is another chance to get better.</p><div className="heatmap" aria-label="Submission activity for the last 91 days">{stats.data.activity.map(day => <div tabIndex={0} role="img" aria-label={`${day.date}: ${day.count} submissions`} title={`${day.date}: ${day.count} submissions`} key={day.date} className={`heatmap-cell level-${Math.min(day.count, 4)}`} />)}</div><div className="heatmap-legend"><span>Less</span>{[0, 1, 2, 3, 4].map(level => <i className={`heatmap-cell level-${level}`} key={level} />)}<span>More</span></div><div className="mode-bar-label"><span>Hands-on <strong>{stats.data.manual_attempts}</strong></span><span>AI assist <strong>{stats.data.ai_attempts}</strong></span></div><div className="mode-bar"><span style={{ width: `${stats.data.attempts ? stats.data.manual_attempts / stats.data.attempts * 100 : 0}%` }} /></div></section></div>
      <section className="surface achievements"><div className="surface-heading"><h2>Milestones along the way</h2><Award size={17} /></div><div className="achievement-grid">{stats.data.achievements.map(item => <div key={item.name} className={`achievement ${item.unlocked ? 'unlocked' : ''}`}><span><Award size={25} /></span><strong>{item.name}</strong><p>{item.description}</p><small>{item.unlocked ? 'Unlocked' : 'Keep debugging'}</small></div>)}</div></section>
    </>}
    <section className="surface platform-stats"><div className="surface-heading"><h2>The bigger picture</h2><span className="small-tag">PLATFORM ACTIVITY</span></div>{platform.isError ? <ErrorState error={platform.error} /> : !platform.data ? <Loading /> : <><div className="platform-metrics"><div><span>Monthly active debuggers</span><strong>{platform.data.monthly_active_users}</strong><small>Active in the last 30 days</small></div><div><span>7-day return rate</span><strong>{platform.data.retention_7d == null ? '—' : `${platform.data.retention_7d}%`}</strong><small>{platform.data.retention_cohort_size ? `${platform.data.retention_cohort_size} eligible debuggers` : 'Available after the first 7-day cohort'}</small></div><div><span>Manual turnaround · P95</span><strong>{ms(platform.data.manual_p95_ms)}</strong><small>Target &lt; 2.5 seconds</small></div><div><span>AI turnaround · P95</span><strong>{ms(platform.data.ai_p95_ms)}</strong><small>Target &lt; 5 seconds</small></div></div><p className="metric-footnote">Turnaround includes queue time and evaluation. Completion and mode counts use full, evaluated submissions; infrastructure errors and public test runs are excluded.</p></>}</section>
  </div>;
}

function Profile({ user }: { user: User }) {
  const [editing, setEditing] = useState(false);
  const [bio, setBio] = useState(user.bio);
  const [saving, setSaving] = useState(false);
  const client = useQueryClient();
  async function save() {
    setSaving(true);
    try { await api('/auth/profile', { method: 'PATCH', body: JSON.stringify({ bio }) }); await client.invalidateQueries({ queryKey: ['session'] }); setEditing(false); toast.success('Profile updated.'); }
    catch (error) { toast.error((error as Error).message); }
    finally { setSaving(false); }
  }
  return <div className="profile-strip"><Avatar name={user.username} /><div><strong>@{user.username}</strong>{editing ? <div className="bio-edit"><input aria-label="Your bio" maxLength={280} value={bio} onChange={event => setBio(event.target.value)} /><button disabled={saving} className="button primary small" onClick={() => void save()}>Save</button><button className="button ghost small" onClick={() => setEditing(false)}>Cancel</button></div> : <p>{user.bio || 'Curiosity is a good place to start.'}</p>}</div>{!editing && <button className="text-link" onClick={() => setEditing(true)}><Pencil size={13} />Edit bio</button>}</div>;
}
