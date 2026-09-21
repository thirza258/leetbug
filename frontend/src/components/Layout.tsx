import { ArrowUpRight, BarChart3, BookOpen, ChevronRight, CircleHelp, GraduationCap, LayoutGrid, LogOut, Menu, MessageSquare, PenLine, ShieldCheck, Trophy, X } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { toast } from 'sonner';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import type { Meta } from '../types';
import { useAuth } from '../lib/auth';
import { Avatar, Logo } from './ui';
import ThemeToggle from './ThemeToggle';

const links = [
  { to: '/', label: 'Problem library', icon: LayoutGrid },
  { to: '/courses', label: 'Courses', icon: GraduationCap },
  { to: '/progress', label: 'My progress', icon: BarChart3 },
  { to: '/submissions', label: 'Submissions', icon: BookOpen },
  { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
  { to: '/discussions', label: 'Discussions', icon: MessageSquare },
];
export default function Layout() {
  const { user, logout } = useAuth();
  const meta = useQuery({ queryKey: ['meta'], queryFn: () => api<Meta>('/meta') });
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const workspace = location.pathname.startsWith('/problems/');
  const title = workspace ? 'Debugging workspace' : location.pathname.startsWith('/courses') ? 'Courses' : links.find(link => link.to === location.pathname)?.label || 'Community';
  return <div className={`app-shell ${workspace ? 'workspace-shell' : ''}`}>
    <a href="#main-content" className="skip-link">Skip to content</a>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <div className="sidebar-brand"><Logo /><button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={20} /></button></div>
      <span className="nav-label">WORKSPACE</span>
      <nav aria-label="Main navigation">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18} /><span>{label}</span>{to === '/' && <span className="nav-count">{meta.data?.problem_count ?? '—'}</span>}</NavLink>)}
      <NavLink to="/submit-problem" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><PenLine size={18} /><span>Submit a problem</span></NavLink>
      {user?.is_admin && <NavLink to="/admin" onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><ShieldCheck size={18} /><span>Admin panel</span></NavLink>}</nav>
      <div className="sidebar-bottom">
        <NavLink to="/guide" className="nav-link" onClick={() => setOpen(false)}><CircleHelp size={18} /><span>Getting started</span></NavLink>
        <div className="sidebar-user">{user ? <><NavLink to="/progress" className="user-link" onClick={() => setOpen(false)}><Avatar name={user.username} /><div><strong>{user.username}</strong><span>Your account</span></div></NavLink><button title="Sign out" aria-label="Sign out" className="icon-button" onClick={() => { logout().catch(error => toast.error(error.message)); }}><LogOut size={16} /></button></> : <NavLink className="button secondary full" to="/login">Sign in / Join LeetBug <ArrowUpRight size={15} /></NavLink>}</div>
      </div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-only" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu size={20} /></button><span>Workspace</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="topbar-right"><ThemeToggle />{user ? <Avatar name={user.username} size="small" /> : <NavLink to="/register" className="button primary small">Start debugging <ArrowUpRight size={14} /></NavLink>}</div></header>
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      {!workspace && <footer className="footer"><NavLink to="/guide">Help &amp; guide</NavLink><span>LeetBug <span className="muted">/</span> v1.0</span></footer>}
    </div>
  </div>;
}
