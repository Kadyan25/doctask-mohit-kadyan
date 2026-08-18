import type { DeliverableSection } from "../api/client";

export function DeliverableView({ sections }: { sections: DeliverableSection[] }) {
  if (sections.length === 0) {
    return <p className="empty-state">No deliverable yet — start a run first.</p>;
  }
  return (
    <div>
      {sections.map((s) => (
        <details key={s.section_key} open className="section-block">
          <summary>
            {s.section_key}
            <span className="version-tag">v{s.version}</span>
          </summary>
          <pre>{s.content}</pre>
        </details>
      ))}
    </div>
  );
}
