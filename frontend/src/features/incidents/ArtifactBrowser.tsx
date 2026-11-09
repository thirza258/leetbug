import { Activity, Boxes, CheckCircle2, Database, FileCode2, FileText, GitCommitHorizontal, ListTree, ScrollText, Settings2 } from 'lucide-react';
import { useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { artifactNames } from './format';
import { LogsViewer, MetricsViewer, TracesViewer } from './Observability';
import { ArchitectureDiagram, DatabaseViewer, DiffViewer, TextArtifact } from './SystemContext';
import type { Artifact, ArtifactType } from './types';

const icons: Record<ArtifactType, LucideIcon> = {
  logs: ScrollText, metrics: Activity, traces: ListTree, database: Database, config: Settings2, diff: GitCommitHorizontal,
  architecture: Boxes, source: FileCode2, api_contract: FileText, runbook: FileText,
};

function ArtifactView({ artifact }: { artifact: Artifact }) {
  const data = artifact.data;
  switch (artifact.type) {
    case 'logs': return <LogsViewer entries={data.entries ?? []} />;
    case 'metrics': return <MetricsViewer series={data.series ?? []} annotations={data.annotations} />;
    case 'traces': return <TracesViewer traces={data.traces ?? []} />;
    case 'database': return <DatabaseViewer tables={data.tables ?? []} />;
    case 'diff': return <DiffViewer data={data} />;
    case 'architecture': return <ArchitectureDiagram nodes={data.nodes} edges={data.edges} />;
    default: return <TextArtifact data={data} />;
  }
}

/** Lists artifacts of the given types; opening one is an explicit investigation step that is recorded. */
export default function ArtifactBrowser({ artifacts, types, viewed, onOpen, empty }: {
  artifacts: Artifact[]; types: ArtifactType[]; viewed: Record<string, string>; onOpen: (artifact: Artifact) => void; empty: string;
}) {
  const visible = artifacts.filter(artifact => types.includes(artifact.type));
  const [selected, setSelected] = useState<string | null>(null);
  const current = visible.find(artifact => artifact.id === selected);
  if (!visible.length) return <p className="muted">{empty}</p>;
  return <div className="artifact-browser">
    <nav className="artifact-list" aria-label="Artifacts">{visible.map(artifact => {
      const Icon = icons[artifact.type];
      return <button key={artifact.id} className={artifact.id === selected ? 'active' : ''} aria-current={artifact.id === selected ? 'true' : undefined}
        onClick={() => { setSelected(artifact.id); onOpen(artifact); }}>
        <Icon size={15} /><span><strong>{artifact.title}</strong><small>{artifactNames[artifact.type]}</small></span>
        {viewed[artifact.id] && <CheckCircle2 size={13} className="artifact-seen" aria-label="Inspected" />}
      </button>;
    })}</nav>
    <section className="artifact-view" aria-live="polite">{current ? <>
      <div className="artifact-view-head"><h3>{current.title}</h3>{current.description && <p className="muted">{current.description}</p>}</div>
      <ArtifactView key={current.id} artifact={current} />
    </> : <div className="artifact-empty"><ListTree size={22} /><p>Select an artifact to inspect it. Each artifact you open counts toward your investigation.</p></div>}</section>
  </div>;
}
