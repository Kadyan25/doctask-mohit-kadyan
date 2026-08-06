import type { DeliverableSection } from "../api/client";

export function DeliverableView({ sections }: { sections: DeliverableSection[] }) {
  if (sections.length === 0) {
    return <p>No deliverable yet — start a run first.</p>;
  }
  return (
    <div>
      {sections.map((s) => (
        <details key={s.section_key} open style={{ marginBottom: "0.75rem" }}>
          <summary style={{ fontWeight: 600, cursor: "pointer" }}>
            {s.section_key} (v{s.version})
          </summary>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit", fontSize: "0.9rem" }}>{s.content}</pre>
        </details>
      ))}
    </div>
  );
}
