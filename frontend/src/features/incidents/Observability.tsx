import { useMemo, useState } from 'react';
import { Search, X } from 'lucide-react';
import { clock, compactNumber, toTime } from './format';
import type { LogEntry, MetricAnnotation, MetricSeries, Trace } from './types';

const LEVELS = ['debug', 'info', 'warn', 'warning', 'error', 'fatal', 'critical'];
const MAX_ROWS = 300;

export function LogsViewer({ entries }: { entries: LogEntry[] }) {
  const [level, setLevel] = useState('');
  const [service, setService] = useState('');
  const [text, setText] = useState('');
  const [trace, setTrace] = useState('');
  const services = useMemo(() => [...new Set(entries.map(entry => entry.service))].sort(), [entries]);
  const levels = useMemo(() => [...new Set(entries.map(entry => entry.level.toLowerCase()))]
    .sort((a, b) => LEVELS.indexOf(a) - LEVELS.indexOf(b)), [entries]);
  const needle = text.trim().toLowerCase();
  const rows = entries.filter(entry => (!level || entry.level.toLowerCase() === level) && (!service || entry.service === service)
    && (!trace || entry.trace_id === trace)
    && (!needle || `${entry.message} ${JSON.stringify(entry.fields ?? {})}`.toLowerCase().includes(needle)));
  return <div className="incident-logs">
    <div className="incident-filters">
      <label className="search-input"><Search size={15} /><input aria-label="Search log messages" placeholder="Search messages and fields…" value={text} onChange={event => setText(event.target.value)} /></label>
      <select aria-label="Log level" value={level} onChange={event => setLevel(event.target.value)}><option value="">All levels</option>{levels.map(value => <option key={value} value={value}>{value}</option>)}</select>
      <select aria-label="Service" value={service} onChange={event => setService(event.target.value)}><option value="">All services</option>{services.map(value => <option key={value} value={value}>{value}</option>)}</select>
      {trace && <button className="filter-chip" onClick={() => setTrace('')}>trace {trace}<X size={12} /></button>}
    </div>
    <p className="incident-count">{rows.length} of {entries.length} entries{rows.length > MAX_ROWS ? ` · showing the first ${MAX_ROWS}` : ''}</p>
    <div className="incident-table-wrap"><table className="incident-log-table">
      <thead><tr><th>TIME</th><th>LEVEL</th><th>SERVICE</th><th>MESSAGE</th><th>TRACE</th></tr></thead>
      <tbody>{rows.slice(0, MAX_ROWS).map((entry, index) => <tr key={`${entry.ts}:${index}`} className={`log-${entry.level.toLowerCase()}`}>
        <td className="mono">{clock(entry.ts)}</td>
        <td><span className={`log-level ${entry.level.toLowerCase()}`}>{entry.level}</span></td>
        <td>{entry.service}</td>
        <td><span>{entry.message}</span>{entry.fields && Object.keys(entry.fields).length > 0 && <span className="log-fields">{Object.entries(entry.fields).map(([key, value]) => <code key={key}>{key}={typeof value === 'string' ? value : JSON.stringify(value)}</code>)}</span>}</td>
        <td>{entry.trace_id ? <button className="text-link mono" title="Show only this trace" onClick={() => setTrace(entry.trace_id!)}>{entry.trace_id}</button> : <span className="muted">—</span>}</td>
      </tr>)}</tbody>
    </table></div>
  </div>;
}

const WIDTH = 640;
const HEIGHT = 180;
const PAD = { left: 48, right: 14, top: 14, bottom: 28 };

function MetricChart({ series, annotations }: { series: MetricSeries; annotations: MetricAnnotation[] }) {
  const points = series.points.map(([x, y], index) => ({ x: Number.isNaN(toTime(x)) ? index : toTime(x), y, label: x }));
  const xs = points.map(point => point.x);
  const ys = points.map(point => point.y);
  const [minX, maxX] = [Math.min(...xs), Math.max(...xs)];
  let [minY, maxY] = [Math.min(...ys), Math.max(...ys)];
  if (minY === maxY) { minY -= 1; maxY += 1; }
  const spanX = maxX - minX || 1;
  const px = (x: number) => PAD.left + (x - minX) / spanX * (WIDTH - PAD.left - PAD.right);
  const py = (y: number) => HEIGHT - PAD.bottom - (y - minY) / (maxY - minY) * (HEIGHT - PAD.top - PAD.bottom);
  const line = points.map((point, index) => `${index ? 'L' : 'M'}${px(point.x).toFixed(1)},${py(point.y).toFixed(1)}`).join(' ');
  const area = `${line} L${px(maxX).toFixed(1)},${HEIGHT - PAD.bottom} L${px(minX).toFixed(1)},${HEIGHT - PAD.bottom} Z`;
  const marks = annotations.map(note => ({ ...note, x: toTime(note.at) })).filter(note => !Number.isNaN(note.x) && note.x >= minX && note.x <= maxX);
  const last = points.at(-1);
  return <figure className="metric-card">
    <figcaption><strong>{series.name}</strong><span>{series.unit ?? ''}</span><span className="metric-range">min {compactNumber(Math.min(...ys))} · max {compactNumber(Math.max(...ys))} · last {last ? compactNumber(last.y) : '—'}</span></figcaption>
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${series.name}: ${points.length} points from ${compactNumber(ys[0])} to ${last ? compactNumber(last.y) : ''} ${series.unit ?? ''}`}>
      <line className="metric-axis" x1={PAD.left} x2={WIDTH - PAD.right} y1={HEIGHT - PAD.bottom} y2={HEIGHT - PAD.bottom} />
      <text className="metric-tick" x={PAD.left - 6} y={py(maxY) + 4} textAnchor="end">{compactNumber(maxY)}</text>
      <text className="metric-tick" x={PAD.left - 6} y={py(minY) + 4} textAnchor="end">{compactNumber(minY)}</text>
      <text className="metric-tick" x={PAD.left} y={HEIGHT - 8}>{clock(points[0]?.label ?? '')}</text>
      <text className="metric-tick" x={WIDTH - PAD.right} y={HEIGHT - 8} textAnchor="end">{clock(last?.label ?? '')}</text>
      <path className="metric-area" d={area} />
      <path className="metric-line" d={line} />
      {marks.map(note => <g key={`${note.label}:${note.x}`} className="metric-annotation">
        <line x1={px(note.x)} x2={px(note.x)} y1={PAD.top} y2={HEIGHT - PAD.bottom} />
        <text x={Math.min(px(note.x) + 4, WIDTH - 90)} y={PAD.top + 10}>{note.label}</text>
      </g>)}
    </svg>
    <details className="metric-data"><summary>Show data</summary><table><tbody>{points.map((point, index) => <tr key={index}><td className="mono">{clock(point.label)}</td><td className="mono">{point.y}</td></tr>)}</tbody></table></details>
  </figure>;
}

export function MetricsViewer({ series, annotations = [] }: { series: MetricSeries[]; annotations?: MetricAnnotation[] }) {
  return <div className="metric-grid">{series.filter(row => row.points.length).map(row => <MetricChart key={row.name} series={row} annotations={annotations} />)}</div>;
}

interface Row { span: Trace['spans'][number]; depth: number }
function orderSpans(trace: Trace): Row[] {
  const children = new Map<string, Trace['spans']>();
  const ids = new Set(trace.spans.map(span => span.span_id));
  for (const span of trace.spans) {
    const parent = span.parent_id && ids.has(span.parent_id) ? span.parent_id : '';
    children.set(parent, [...(children.get(parent) ?? []), span]);
  }
  const rows: Row[] = [];
  const seen = new Set<string>();
  const visit = (parent: string, depth: number) => {
    for (const span of [...(children.get(parent) ?? [])].sort((a, b) => a.start_ms - b.start_ms)) {
      if (seen.has(span.span_id)) continue;
      seen.add(span.span_id);
      rows.push({ span, depth });
      visit(span.span_id, depth + 1);
    }
  };
  visit('', 0);
  return rows;
}

export function TracesViewer({ traces }: { traces: Trace[] }) {
  const [selected, setSelected] = useState(traces[0]?.trace_id ?? '');
  const trace = traces.find(item => item.trace_id === selected) ?? traces[0];
  if (!trace) return <p className="muted">No traces were captured.</p>;
  const rows = orderSpans(trace);
  const start = Math.min(...trace.spans.map(span => span.start_ms));
  const end = Math.max(...trace.spans.map(span => span.start_ms + span.duration_ms));
  const total = end - start || 1;
  return <div className="incident-traces">
    <div className="trace-picker" role="group" aria-label="Choose a trace">{traces.map(item => {
      const failed = item.spans.some(span => (span.status ?? 'ok') !== 'ok');
      const root = orderSpans(item)[0]?.span;
      return <button key={item.trace_id} className={item.trace_id === trace.trace_id ? 'active' : ''} aria-pressed={item.trace_id === trace.trace_id} onClick={() => setSelected(item.trace_id)}>
        <span className={`trace-dot ${failed ? 'error' : 'ok'}`} /><span className="mono">{item.trace_id}</span><small>{root ? `${root.service} · ${root.name}` : ''}</small>
      </button>;
    })}</div>
    <div className="trace-waterfall" aria-label={`Spans of trace ${trace.trace_id}`}>
      <div className="trace-row trace-head"><span>SPAN</span><span>TIMELINE · {total} ms</span></div>
      {rows.map(({ span, depth }) => <details key={span.span_id} className={`trace-span ${(span.status ?? 'ok') !== 'ok' ? 'error' : ''}`}>
        <summary className="trace-row">
          <span className="trace-label" style={{ paddingLeft: depth * 14 }}><strong>{span.service}</strong> {span.name}</span>
          <span className="trace-track"><span className="trace-bar" style={{ left: `${(span.start_ms - start) / total * 100}%`, width: `${Math.max(0.6, span.duration_ms / total * 100)}%` }} /><span className="trace-duration">{span.duration_ms} ms</span></span>
        </summary>
        <dl className="trace-attributes">{[['status', span.status ?? 'ok'], ['start', `+${span.start_ms - start} ms`], ...Object.entries(span.attributes ?? {})]
          .map(([key, value]) => <div key={String(key)}><dt>{String(key)}</dt><dd>{typeof value === 'string' ? value : JSON.stringify(value)}</dd></div>)}</dl>
      </details>)}
    </div>
  </div>;
}
