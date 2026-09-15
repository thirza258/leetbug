import { ArrowLeft, ArrowRight, Eye, EyeOff, LoaderCircle } from 'lucide-react';
import { useState } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../lib/auth';
import { Logo } from '../components/ui';
import ThemeToggle from '../components/ThemeToggle';

export default function AuthPage({ register = false }: { register?: boolean }) {
  const { user, authenticate } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [visible, setVisible] = useState(false);
  const next = params.get('next');
  const destination = next?.startsWith('/') && !next.startsWith('//') ? next : '/';
  if (user) return <Navigate to={destination} replace />;
  async function submit(event: React.SubmitEvent<HTMLFormElement>) {
    event.preventDefault(); setError(''); setBusy(true);
    const form = new FormData(event.currentTarget);
    const data = Object.fromEntries(form.entries()) as Record<string, string>;
    try { await authenticate(register ? 'register' : 'login', data); navigate(destination, { replace: true }); }
    catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="auth-page"><header className="auth-header"><Logo /><ThemeToggle /></header><div className="auth-form-side"><Link to="/" className="text-link auth-back"><ArrowLeft size={15} /> Back to the library</Link><div className="auth-form-wrap"><h2>{register ? 'Create your account' : 'Welcome back.'}</h2><p>{register ? 'Save your fixes, track progress, and learn with the community.' : 'Sign in to continue your debugging practice.'}</p><form onSubmit={event => void submit(event)}>
      {register && <label>Username<input name="username" autoComplete="username" minLength={3} maxLength={30} pattern="[a-zA-Z0-9_]+" required placeholder="your_debugger_name" /><small>3–30 letters, numbers, or underscores.</small></label>}
      <label>Email address<input name="email" type="email" autoComplete="email" required placeholder="you@example.com" /></label><label>Password<div className="password-field"><input name="password" type={visible ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} minLength={register ? 10 : 1} maxLength={128} required placeholder={register ? 'At least 10 characters' : 'Your password'} /><button type="button" className="icon-button" aria-label={visible ? 'Hide password' : 'Show password'} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={17} /> : <Eye size={17} />}</button></div></label>
      {error && <div className="inline-error" role="alert">{error}</div>}<button className="button primary full" disabled={busy}>{busy ? <LoaderCircle size={17} className="spin" /> : <>{register ? 'Start your debugging journey' : 'Sign in'}<ArrowRight size={17} /></>}</button>
    </form><p className="auth-switch">{register ? 'Already part of the club?' : 'New to LeetBug?'} <Link to={`${register ? '/login' : '/register'}${next ? `?next=${encodeURIComponent(next)}` : ''}`}>{register ? 'Sign in' : 'Create an account'}</Link></p><p className="auth-fineprint">Your code, your pace. Learn by doing.</p></div></div></div>;
}

