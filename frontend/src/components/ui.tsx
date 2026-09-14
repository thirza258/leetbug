import { AlertCircle, ArrowRight, Bug, Check, CheckCircle2, LoaderCircle, LockKeyhole, X } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { statusNames } from '../lib/constants';
import type { Status } from '../types';

export function Logo() {
  return <Link className="brand" to="/" aria-label="LeetBug home"><span className="brand-icon"><Bug size={22} strokeWidth={2} /></span><span>leet<span className="brand-light">bug</span><span className="brand-dot">.</span></span></Link>;
}
export function Loading({ label = 'Loading your workspace…' }: { label?: string }) {
  return <div className="loading" role="status"><LoaderCircle size={23} className="spin" /><span>{label}</span></div>;
}
export function ErrorState({ error, retry }: { error: Error | null; retry?: () => void }) {
  return <div className="error-box" role="alert"><AlertCircle size={19} /><div><strong>We hit a snag</strong><p>{error?.message || 'Please try again.'}</p>{retry && <button className="button secondary small" onClick={retry}>Try again</button>}</div></div>;
}
export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: string; children: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon || <Bug size={28} />}</div><h3>{title}</h3><div>{children}</div></div>;
}
export function SignInCard({ title = 'Make your debugging count' }: { title?: string }) {
  const location = useLocation();
  return <EmptyState icon={<LockKeyhole size={28} />} title={title}><p>Sign in to save your fixes, track progress, and join the conversation.</p><Link className="button primary" to={`/login?next=${encodeURIComponent(location.pathname)}`}>Sign in to continue <ArrowRight size={16} /></Link></EmptyState>;
}
export function StatusBadge({ status }: { status: Status }) {
  return <span className={`status-badge ${status}`}>
    {status === 'passed' ? <CheckCircle2 size={13} /> : status === 'queued' || status === 'running' ? <LoaderCircle size={13} className="spin" /> : <X size={13} />}{statusNames[status]}
  </span>;
}
export function Difficulty({ value }: { value: string }) { return <span className={`difficulty ${value}`}><span />{value}</span>; }
export function Avatar({ name, size = '' }: { name: string; size?: string }) { return <span className={`avatar ${size}`}>{name.slice(0, 2).toUpperCase()}</span>; }
export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{action}</div>;
}
export function CheckItem({ children }: { children: ReactNode }) { return <div className="check-item"><Check size={15} />{children}</div>; }

