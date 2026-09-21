import { ArrowLeft, Plus, Send, X } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from 'sonner';
import { submitProblem } from '../lib/api';
import { useAuth } from '../lib/auth';
import { SignInCard, PageHeading } from '../components/ui';
import type { Category, Language } from '../types';

const categories: { value: Category; label: string }[] = [
  { value: 'runtime', label: 'Runtime errors' },
  { value: 'logic', label: 'Logic errors' },
  { value: 'business', label: 'Business flow' },
  { value: 'edge', label: 'Edge & corner cases' },
  { value: 'system_design', label: 'System design' },
];
const languages: { value: Language; label: string }[] = [
  { value: 'python', label: 'Python' },
  { value: 'java', label: 'Java' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'cpp', label: 'C++' },
  { value: 'go', label: 'Go' },
];

export default function SubmitProblem() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [testCases, setTestCases] = useState([{ input: '', expected: '' }]);
  const [tags, setTags] = useState<string[]>([]);
  const [tagInput, setTagInput] = useState('');

  if (!user) return <div className="page"><SignInCard title="Sign in to submit a problem" /></div>;

  function addTag() {
    const tag = tagInput.trim().toLowerCase();
    if (tag && tags.length < 5 && !tags.includes(tag)) {
      setTags([...tags, tag]);
      setTagInput('');
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await submitProblem({
        title: form.get('title') as string,
        summary: form.get('summary') as string,
        description: form.get('description') as string,
        category: form.get('category') as string,
        difficulty: form.get('difficulty') as string,
        tags,
        language: form.get('language') as string,
        buggy_code: form.get('buggy_code') as string,
        fixed_code: form.get('fixed_code') as string,
        test_cases: testCases.filter(tc => tc.input.trim() || tc.expected.trim()),
        hint: form.get('hint') as string || '',
      });
      toast.success('Problem submitted! An admin will review it soon.');
      navigate('/');
    } catch (error) {
      toast.error((error as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page narrow-page">
      <Link to="/" className="text-link" style={{ marginBottom: 25 }}><ArrowLeft size={15} /> Back to library</Link>
      <PageHeading eyebrow="CONTRIBUTE" title="Submit a debugging problem" description="Share a buggy code snippet with the community. An admin will review and approve it." />
      <form className="discussion-form" onSubmit={event => void handleSubmit(event)}>
        <div className="surface">
          <div className="surface-heading"><h2>Problem details</h2></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            <label>Title
              <input name="title" required minLength={5} maxLength={150} placeholder="e.g. Off-by-one in binary search" />
            </label>
            <label>Summary
              <input name="summary" required minLength={10} maxLength={500} placeholder="Brief one-line description of the bug" />
            </label>
            <label>Description
              <textarea name="description" required minLength={20} maxLength={10000} rows={6} placeholder="Detailed explanation of the scenario, what the code is supposed to do, and what the bug is..." />
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 15 }}>
              <label>Category
                <select name="category" required>
                  {categories.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </label>
              <label>Difficulty
                <select name="difficulty" required>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </label>
              <label>Language
                <select name="language" required>
                  {languages.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </label>
            </div>
            <label>Tags <span className="muted">(up to 5)</span>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                {tags.map(tag => (
                  <span key={tag} className="filter-chip">{tag}
                    <button type="button" onClick={() => setTags(tags.filter(t => t !== tag))}><X size={12} /></button>
                  </span>
                ))}
                {tags.length < 5 && (
                  <div style={{ display: 'flex', gap: 5 }}>
                    <input value={tagInput} onChange={e => setTagInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addTag(); } }}
                      placeholder="Add tag…" style={{ width: 120, padding: '6px 10px', fontSize: 12 }} />
                    <button type="button" className="icon-button" onClick={addTag}><Plus size={14} /></button>
                  </div>
                )}
              </div>
            </label>
          </div>
        </div>

        <div className="surface">
          <div className="surface-heading"><h2>Code</h2></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>
            <label>Buggy code
              <textarea name="buggy_code" required minLength={10} maxLength={50000} rows={10}
                style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}
                placeholder="Paste the buggy code here..." />
            </label>
            <label>Fixed code
              <textarea name="fixed_code" required minLength={10} maxLength={50000} rows={10}
                style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12 }}
                placeholder="Paste the corrected code here..." />
            </label>
            <label>Hint <span className="muted">(optional)</span>
              <textarea name="hint" maxLength={2000} rows={3} placeholder="A hint to guide the debugger..." />
            </label>
          </div>
        </div>

        <div className="surface">
          <div className="surface-heading"><h2>Test cases</h2></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {testCases.map((tc, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr auto', gap: 10, alignItems: 'end' }}>
                <label>Input
                  <input value={tc.input} onChange={e => {
                    const next = [...testCases]; next[i] = { ...next[i], input: e.target.value }; setTestCases(next);
                  }} placeholder='e.g. [1, 2, 3]' />
                </label>
                <label>Expected output
                  <input value={tc.expected} onChange={e => {
                    const next = [...testCases]; next[i] = { ...next[i], expected: e.target.value }; setTestCases(next);
                  }} placeholder='e.g. 6' />
                </label>
                {testCases.length > 1 && (
                  <button type="button" className="icon-button" style={{ marginBottom: 2 }}
                    onClick={() => setTestCases(testCases.filter((_, j) => j !== i))}><X size={16} /></button>
                )}
              </div>
            ))}
            {testCases.length < 20 && (
              <button type="button" className="button secondary small" style={{ alignSelf: 'flex-start' }}
                onClick={() => setTestCases([...testCases, { input: '', expected: '' }])}>
                <Plus size={14} /> Add test case
              </button>
            )}
          </div>
        </div>

        <div className="form-actions">
          <Link to="/" className="button secondary">Cancel</Link>
          <button className="button primary" disabled={busy}>
            {busy ? 'Submitting…' : <><Send size={15} /> Submit for review</>}
          </button>
        </div>
      </form>
    </div>
  );
}
