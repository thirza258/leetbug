import { useState } from 'react';
import type { HistogramBucket } from './types';

// Single-series charts: one accent hue (no legend; the caption names the series), thin marks with a
// 4px rounded data end and a square baseline, hairline axes, hover/focus tooltips, and a table view.

const W = 600, H = 220, PAD = { top: 14, right: 8, bottom: 30, left: 34 };

function niceMax(value: number) {
  if (value <= 5) return Math.max(1, value);
  const step = [1, 2, 5, 10, 20, 50, 100, 200, 500].find(candidate => value / candidate <= 5) ?? 1000;
  return Math.ceil(value / step) * step;
}

function columnPath(x: number, y: number, width: number, height: number) {
  const r = Math.min(4, width / 2, height);
  return `M${x},${y + height}L${x},${y + r}Q${x},${y} ${x + r},${y}L${x + width - r},${y}Q${x + width},${y} ${x + width},${y + r}L${x + width},${y + height}Z`;
}

export function ScoreHistogram({ buckets, caption }: { buckets: HistogramBucket[]; caption: string }) {
  const [active, setActive] = useState<number | null>(null);
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0);
  const top = niceMax(Math.max(0, ...buckets.map(bucket => bucket.count)));
  const plotW = W - PAD.left - PAD.right, plotH = H - PAD.top - PAD.bottom;
  const slot = plotW / Math.max(1, buckets.length);
  const barW = Math.min(24, slot - 2);
  const ticks = top <= 5 ? Array.from({ length: top + 1 }, (_, index) => index) : [0, top / 2, top];
  const y = (value: number) => PAD.top + plotH - (value / top) * plotH;
  const shown = active == null ? null : buckets[active];
  return <figure className="org-figure">
    <figcaption>{caption}</figcaption>
    <svg className="org-chart" viewBox={`0 0 ${W} ${H}`} role="group" aria-label={`${caption}. ${total} sessions.`}>
      {ticks.map(tick => <g key={tick}><line className="grid" x1={PAD.left} x2={W - PAD.right} y1={y(tick)} y2={y(tick)} /><text className="tick" x={PAD.left - 8} y={y(tick) + 4} textAnchor="end">{tick}</text></g>)}
      {buckets.map((bucket, index) => {
        const height = (bucket.count / top) * plotH;
        const x = PAD.left + index * slot + (slot - barW) / 2;
        const label = `${bucket.from}–${bucket.to}%: ${bucket.count} session${bucket.count === 1 ? '' : 's'}`;
        return <g key={bucket.from} tabIndex={0} role="img" aria-label={label}
          onPointerEnter={() => setActive(index)} onPointerLeave={() => setActive(null)} onFocus={() => setActive(index)} onBlur={() => setActive(null)}>
          <rect className="hit" x={PAD.left + index * slot} y={PAD.top} width={slot} height={plotH} />
          {bucket.count > 0 && <path className="bar" d={columnPath(x, y(bucket.count), barW, height)} />}
          <text className="tick" x={PAD.left + index * slot + slot / 2} y={H - PAD.bottom + 16} textAnchor="middle">{index % 2 === 0 || buckets.length <= 6 ? bucket.from : ''}</text>
        </g>;
      })}
      <line className="baseline" x1={PAD.left} x2={W - PAD.right} y1={PAD.top + plotH} y2={PAD.top + plotH} />
    </svg>
    {shown && active != null && <div className="org-tooltip" style={{ left: `${((PAD.left + active * slot + slot / 2) / W) * 100}%`, top: `${(y(shown.count) / H) * 100}%` }}>
      <strong>{shown.count} session{shown.count === 1 ? '' : 's'}</strong><span>Score {shown.from}–{shown.to}%</span></div>}
    <details className="org-table-view"><summary>Table view</summary><table className="data-table"><thead><tr><th>SCORE RANGE</th><th className="org-num">SESSIONS</th></tr></thead>
      <tbody>{buckets.map(bucket => <tr key={bucket.from}><td>{bucket.from}–{bucket.to}%</td><td className="org-num">{bucket.count}</td></tr>)}</tbody></table></details>
  </figure>;
}

export interface BarRow { id: string; label: string; value: number | null; detail?: string }

export function HorizontalBars({ rows, caption, empty = 'Not assessed' }: { rows: BarRow[]; caption: string; empty?: string }) {
  return <figure className="org-figure">
    <figcaption>{caption}</figcaption>
    <ul className="org-hbars">{rows.map(row => {
      const value = row.value == null ? null : Math.max(0, Math.min(100, row.value));
      const text = value == null ? empty : `${Math.round(value)}%`;
      return <li key={row.id} className="org-hbar" tabIndex={0} aria-label={`${row.label}: ${text}${row.detail ? `, ${row.detail}` : ''}`} title={row.detail}>
        <span className="org-hbar-name">{row.label}{row.detail && <small>{row.detail}</small>}</span>
        <span className="org-hbar-track" aria-hidden="true">{value != null && value > 0 && <span className="org-hbar-fill" style={{ width: `${value}%` }} />}</span>
        <span className="org-hbar-value">{text}</span>
      </li>;
    })}</ul>
  </figure>;
}
