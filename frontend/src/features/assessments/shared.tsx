import { Bot, Lightbulb, Timer } from 'lucide-react';
import { aiNames, hintNames, minutes, score } from './format';
import type { AssistancePolicy } from './types';

export function PolicyBadges({ policy, duration }: { policy: AssistancePolicy; duration?: number }) {
  return <div className="asm-badges">
    {duration != null && <span className="small-tag"><Timer size={12} />{minutes(duration)}</span>}
    <span className={`small-tag ${policy.ai === 'disabled' ? '' : 'asm-tag-open'}`}><Bot size={12} />{aiNames[policy.ai]}</span>
    <span className={`small-tag ${policy.hints === 'disabled' ? '' : 'asm-tag-open'}`}><Lightbulb size={12} />{hintNames[policy.hints]}</span>
  </div>;
}

export function ScoreBar({ label, value, detail }: { label: string; value: number | null | undefined; detail?: string }) {
  return <div className="asm-score-bar">
    <div><strong>{label}</strong><span>{score(value)}</span></div>
    <div className="progress-track" role="img" aria-label={`${label}: ${score(value)}`}><span className="purple" style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }} /></div>
    {detail && <small>{detail}</small>}
  </div>;
}
