import { ArrowUpRight, BarChart3, BookOpen, ChevronRight, CircleHelp, Github, LayoutGrid, LogOut, Menu, MessageSquare, Trophy, X } from 'lucide-react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { toast } from 'sonner';
import { useAuth } from '../lib/auth';
import { Avatar, Logo } from './ui';

const links = [
  { to: '/', label: 'Problem library', icon: LayoutGrid },
  { to: '/progress', label: 'My progress', icon: BarChart3 },
  { to: '/submissions', label: 'Submissions', icon: BookOpen },
  { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
  { to: '/discussions', label: 'Discussions', icon: MessageSquare },
];
export default function Layout() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const workspace = location.pathname.startsWith('/problems/');
  const title = workspace ? 'Debugging workspace' : links.find(link => link.to === location.pathname)?.label || 'Community';
  return <div className={`app-shell ${workspace ? 'workspace-shell' : ''}`}>
    <a href="#main-content" className="skip-link">Skip to content</a>
    {open && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setOpen(false)} />}
    <aside className={`sidebar ${open ? 'is-open' : ''}`}>
      <div className="sidebar-brand"><Logo /><button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Close navigation"><X size={20} /></button></div>
      <span className="nav-label">YOUR DEBUGGING SPACE</span>
      <nav aria-label="Main navigation">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><Icon size={18} /><span>{label}</span>{to === '/' && <span className="nav-count">12</span>}</NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="practice-note"><span className="tiny-orbit"><Github size={18} /></span><strong>Read. Reason. Repair.</strong><p>Great engineers don’t just write code. They know how to fix it.</p><NavLink to="/guide">How LeetBug works <ArrowUpRight size={14} /></NavLink></div>
        <NavLink to="/guide" className="nav-link"><CircleHelp size={18} /><span>Getting started</span></NavLink>
        <div className="sidebar-user">{user ? <><NavLink to="/progress" className="user-link"><Avatar name={user.username} /><div><strong>{user.username}</strong><span>Debugging in progress</span></div></NavLink><button title="Sign out" aria-label="Sign out" className="icon-button" onClick={() => { logout().catch(error => toast.error(error.message)); }}><LogOut size={16} /></button></> : <NavLink className="button secondary full" to="/login">Sign in / Join LeetBug <ArrowUpRight size={15} /></NavLink>}</div>
      </div>
    </aside>
    <div className="main-shell"><header className="topbar"><div className="breadcrumb"><button className="icon-button mobile-only" aria-label="Open navigation" onClick={() => setOpen(true)}><Menu size={20} /></button><span>Workspace</span><ChevronRight size={14} /><strong>{title}</strong></div><div className="topbar-right"><span className="live-label"><i />A little better, every bug.</span>{user ? <Avatar name={user.username} size="small" /> : <NavLink to="/register" className="button primary small">Start debugging <ArrowUpRight size={14} /></NavLink>}</div></header>
      <main id="main-content" tabIndex={-1}><Outlet /></main>
      {!workspace && <footer className="footer"><span>Built for the other half of programming.</span><span>LeetBug <span className="muted">/</span> v1.0</span></footer>}
    </div>
  </div>;
}

