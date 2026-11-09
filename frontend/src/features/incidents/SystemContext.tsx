import { FileCode2, GitCommitHorizontal } from 'lucide-react';
import type { ArchitectureEdge, ArchitectureNode, ArtifactData, DataTable } from './types';

export function TextArtifact({ data }: { data: ArtifactData }) {
  return <div className="code-artifact">
    <div className="code-artifact-head"><FileCode2 size={13} /><span className="mono">{data.path || 'file'}</span>{data.language && <span className="small-tag">{data.language}</span>}</div>
    <pre>{(data.content ?? '').split('\n').map((line, index) => <span key={index} className="code-line"><span className="line-number">{index + 1}</span>{line || ' '}{'\n'}</span>)}</pre>
  </div>;
}

export function DiffViewer({ data }: { data: ArtifactData }) {
  const lines = (data.content ?? '').split('\n');
  return <div className="code-artifact">
    <div className="code-artifact-head"><GitCommitHorizontal size={13} /><span>{data.title || 'Deployment diff'}</span>{data.author && <span className="muted">by {data.author}</span>}</div>
    <pre className="diff-view">{lines.map((line, index) => {
      const kind = line.startsWith('+++') || line.startsWith('---') ? 'file' : line.startsWith('@@') ? 'hunk'
        : line.startsWith('+') ? 'added' : line.startsWith('-') ? 'removed' : '';
      return <span key={index} className={`diff-line ${kind}`}>{line || ' '}{'\n'}</span>;
    })}</pre>
  </div>;
}

function cell(value: unknown): string {
  if (value === null || value === undefined) return 'NULL';
  return typeof value === 'string' ? value : JSON.stringify(value);
}

export function DatabaseViewer({ tables }: { tables: DataTable[] }) {
  return <div className="db-tables">{tables.map(table => <section key={table.name} className="db-table">
    <h4 className="mono">{table.name} <span className="muted">· {table.rows.length} row{table.rows.length === 1 ? '' : 's'}</span></h4>
    <div className="incident-table-wrap"><table>
      <thead><tr>{table.columns.map(column => <th key={column} className="mono">{column}</th>)}</tr></thead>
      <tbody>{table.rows.map((row, index) => <tr key={index}>{row.map((value, column) => <td key={column} className={`mono ${value === null ? 'muted' : ''}`}>{cell(value)}</td>)}</tr>)}</tbody>
    </table></div>
  </section>)}</div>;
}

const NODE_W = 150;
const NODE_H = 46;
const GAP_X = 70;
const GAP_Y = 26;
const MARGIN = 16;

/** Layer nodes by their longest distance from a source so request flow reads left to right. */
function layout(nodes: ArchitectureNode[], edges: ArchitectureEdge[]) {
  const layer = new Map(nodes.map(node => [node.id, 0]));
  // Bounded relaxation tolerates cycles: at most |nodes| passes.
  for (let pass = 0; pass < nodes.length; pass++) {
    let changed = false;
    for (const edge of edges) {
      const next = (layer.get(edge.from) ?? 0) + 1;
      if (edge.from !== edge.to && next > (layer.get(edge.to) ?? 0) && next < nodes.length) { layer.set(edge.to, next); changed = true; }
    }
    if (!changed) break;
  }
  const columns = new Map<number, ArchitectureNode[]>();
  for (const node of nodes) columns.set(layer.get(node.id) ?? 0, [...(columns.get(layer.get(node.id) ?? 0) ?? []), node]);
  const positions = new Map<string, { x: number; y: number }>();
  const tallest = Math.max(...[...columns.values()].map(column => column.length));
  for (const [index, column] of columns) {
    const offset = (tallest - column.length) * (NODE_H + GAP_Y) / 2;
    column.forEach((node, row) => positions.set(node.id, { x: MARGIN + index * (NODE_W + GAP_X), y: MARGIN + offset + row * (NODE_H + GAP_Y) }));
  }
  const width = MARGIN * 2 + (Math.max(...columns.keys()) + 1) * (NODE_W + GAP_X) - GAP_X;
  const height = MARGIN * 2 + tallest * (NODE_H + GAP_Y) - GAP_Y;
  return { positions, width, height };
}

export function ArchitectureDiagram({ nodes = [], edges = [] }: { nodes?: ArchitectureNode[]; edges?: ArchitectureEdge[] }) {
  if (!nodes.length) return <p className="muted">No architecture diagram was provided.</p>;
  const { positions, width, height } = layout(nodes, edges);
  return <div className="architecture">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Architecture: ${edges.map(edge => `${edge.from} to ${edge.to}${edge.label ? ` (${edge.label})` : ''}`).join(', ')}`}>
      <defs><marker id="incident-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" className="arch-arrow" /></marker></defs>
      {edges.map((edge, index) => {
        const from = positions.get(edge.from); const to = positions.get(edge.to);
        if (!from || !to) return null;
        const forward = to.x > from.x;
        const x1 = forward ? from.x + NODE_W : from.x + NODE_W / 2; const y1 = forward ? from.y + NODE_H / 2 : from.y + NODE_H;
        const x2 = forward ? to.x : to.x + NODE_W / 2; const y2 = forward ? to.y + NODE_H / 2 : to.y;
        const mid = forward ? (x1 + x2) / 2 : Math.max(x1, x2) + 30;
        const path = forward ? `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}` : `M${x1},${y1} C${mid},${y1 + 30} ${mid},${y2 - 30} ${x2},${y2}`;
        return <g key={index} className="arch-edge"><path d={path} markerEnd="url(#incident-arrow)" />
          {edge.label && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 6} textAnchor="middle">{edge.label}</text>}</g>;
      })}
      {nodes.map(node => {
        const at = positions.get(node.id)!;
        return <g key={node.id} className={`arch-node ${node.kind ?? 'service'}`}>
          <rect x={at.x} y={at.y} width={NODE_W} height={NODE_H} rx={node.kind === 'database' ? 14 : 7} />
          <text x={at.x + NODE_W / 2} y={at.y + 20} textAnchor="middle" className="arch-label">{node.label.length > 20 ? `${node.label.slice(0, 19)}…` : node.label}</text>
          <text x={at.x + NODE_W / 2} y={at.y + 36} textAnchor="middle" className="arch-kind">{node.kind ?? 'service'}</text>
        </g>;
      })}
    </svg>
    <ul className="architecture-edges">{edges.map((edge, index) => <li key={index}><span className="mono">{edge.from}</span> → <span className="mono">{edge.to}</span>{edge.label && <span className="muted"> · {edge.label}</span>}</li>)}</ul>
  </div>;
}
