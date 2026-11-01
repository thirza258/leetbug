import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Shield, FileText, Server, Cpu, ExternalLink, ArrowLeft } from 'lucide-react';

export default function LegalPage() {
  const location = useLocation();
  const initialTab = location.pathname.includes('terms') ? 'terms' : 'privacy';
  const [activeTab, setActiveTab] = useState<'privacy' | 'terms'>(initialTab);

  return (
    <div className="page" style={{ maxWidth: '840px', margin: '0 auto', padding: '32px 20px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Link to="/" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.875rem', color: 'var(--accent, #6366f1)', textDecoration: 'none', marginBottom: '16px' }}>
          <ArrowLeft size={16} /> Back to Problem Library
        </Link>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border, #333)', paddingBottom: '20px' }}>
          <div>
            <h1 style={{ margin: '0 0 6px 0', fontSize: '1.75rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px' }}>
              {activeTab === 'privacy' ? <Shield size={28} color="var(--accent, #6366f1)" /> : <FileText size={28} color="var(--accent, #6366f1)" />}
              {activeTab === 'privacy' ? 'Privacy Policy' : 'Terms of Service'}
            </h1>
            <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--muted, #888)' }}>
              LeetBug Interactive Debugging Platform · Updated November 2026
            </p>
          </div>

          <div style={{ display: 'flex', gap: '6px', background: 'var(--surface-sunken, #1e1e24)', padding: '4px', borderRadius: '8px' }}>
            <button
              type="button"
              onClick={() => setActiveTab('privacy')}
              className={`button small ${activeTab === 'privacy' ? 'primary' : 'ghost'}`}
            >
              Privacy Policy
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('terms')}
              className={`button small ${activeTab === 'terms' ? 'primary' : 'ghost'}`}
            >
              Terms of Service
            </button>
          </div>
        </div>
      </div>

      {activeTab === 'privacy' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', lineHeight: 1.6, fontSize: '0.9rem', color: 'var(--text-secondary, #ccc)' }}>
          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Server size={18} color="var(--accent, #6366f1)" /> 1. 100% Self-Hosted &amp; Local Code Execution
            </h2>
            <p style={{ margin: '0 0 10px 0' }}>
              LeetBug is deployed in a fully self-hosted Docker and PostgreSQL container stack.
              Your account details, code submissions, debugging scratchpads, sandbox test results, and discussion posts
              reside strictly on this private host.
            </p>
            <p style={{ margin: 0 }}>
              There is no third-party telemetry, behavioral tracker, or marketing beacon embedded in LeetBug.
              Your code and solution attempts are never sold or shared with external data brokers.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Cpu size={18} color="var(--accent, #6366f1)" /> 2. AI Mentor &amp; OpenRouter Provider Integration
            </h2>
            <p style={{ margin: '0 0 10px 0' }}>
              LeetBug offers AI-powered debugging hints, failure analysis, and educational code explanations.
              Inference for these intelligent hints is powered by <strong>OpenRouter</strong>.
            </p>
            <p style={{ margin: '0 0 10px 0' }}>
              When you ask the AI assistant for assistance on a problem:
            </p>
            <ul style={{ margin: '0 0 14px 0', paddingLeft: '20px' }}>
              <li>The problem prompt, failing test error message, and your current code attempt are transmitted to OpenRouter.</li>
              <li>Your underlying system container configs and unrelated local database contents are never exposed.</li>
            </ul>
            <div style={{ padding: '14px', borderRadius: '6px', background: 'var(--surface-sunken, #18181f)', border: '1px solid var(--border, #2e2e38)' }}>
              <p style={{ margin: '0 0 8px 0', fontSize: '0.8rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text, #fff)' }}>
                OpenRouter Upstream Policies
              </p>
              <div style={{ display: 'flex', gap: '16px', fontSize: '0.85rem' }}>
                <a href="https://openrouter.ai/privacy" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent, #818cf8)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  OpenRouter Privacy Policy <ExternalLink size={12} />
                </a>
                <a href="https://openrouter.ai/terms" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent, #818cf8)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  OpenRouter Terms of Service <ExternalLink size={12} />
                </a>
              </div>
            </div>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              3. Sandbox Security &amp; Ephemeral Test Containers
            </h2>
            <p style={{ margin: 0 }}>
              Submitted code runs inside unprivileged, ephemeral sandbox containers with strict memory, CPU, and network bounds.
              Execution artifacts are scrubbed immediately upon test evaluation completion.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              4. Privacy Inquiries
            </h2>
            <p style={{ margin: 0 }}>
              For questions regarding privacy, account deletion, or server hosting, contact:{" "}
              <a href="mailto:nevatalapp@gmail.com" style={{ color: 'var(--accent, #818cf8)', fontWeight: 600 }}>
                nevatalapp@gmail.com
              </a>
            </p>
          </section>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', lineHeight: 1.6, fontSize: '0.9rem', color: 'var(--text-secondary, #ccc)' }}>
          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              1. Terms of Use
            </h2>
            <p style={{ margin: 0 }}>
              By accessing or creating an account on this LeetBug installation, you agree to these Terms of Service.
              LeetBug is designed to build debugging intuition, test comprehension, and software analysis skills.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              2. Sandbox Safety &amp; Fair Play
            </h2>
            <p style={{ margin: '0 0 10px 0' }}>
              You agree not to attempt sandbox escapes, exploit kernel vulnerabilities in test runners,
              or mount denial-of-service attacks against the host environment.
            </p>
            <p style={{ margin: 0 }}>
              Solutions submitted to public discussions should be constructive and adhere to respectful collaborative etiquette.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              3. AI Usage Responsibility
            </h2>
            <p style={{ margin: 0 }}>
              Prompts directed to the AI assistant must not violate upstream provider terms as defined in <a href="https://openrouter.ai/terms" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent, #818cf8)' }}>OpenRouter Terms of Service</a>.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              4. Disclaimer of Warranty
            </h2>
            <p style={{ margin: 0 }}>
              The software and problem sandbox are provided on an &ldquo;AS IS&rdquo; basis without warranties of any kind.
              Maintainers are not liable for any issues arising from executing arbitrary code in local environments.
            </p>
          </section>

          <section className="card" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.15rem', color: 'var(--text, #fff)', marginTop: 0, marginBottom: '10px' }}>
              5. Terms Contact
            </h2>
            <p style={{ margin: 0 }}>
              For legal inquiries regarding terms and acceptable use, contact:{" "}
              <a href="mailto:nevatalapp@gmail.com" style={{ color: 'var(--accent, #818cf8)', fontWeight: 600 }}>
                nevatalapp@gmail.com
              </a>
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
