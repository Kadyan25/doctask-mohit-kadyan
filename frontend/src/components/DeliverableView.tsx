import type { DeliverableSection, PendingReviewItem } from "../api/client";
import { conflictMeta, sectionLabel } from "../lib/labels";

// Pull a trailing "(file.md:7)" / "(a.md:8, b.md:8)" off a line so citations can
// render as pills instead of inline parenthetical noise.
const CITE_RE = /\(([^()]*\.[a-z0-9]+:\d+[^()]*)\)\s*$/i;
// A leading "[machine_key]" tag the backend prefixes onto conflict lines.
const TAG_RE = /^\[([^\]]+)\]\s*/;
// "status open" / "status resolved" tail on action-item lines.
const STATUS_RE = /status\s+(open|resolved|closed|done)\b/i;

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, " ").trim();

// Which section keys carry items the reviewer decides on (so we can reflect the
// approve/reject decision live, right in the register).
const REVIEWABLE_SECTIONS = new Set(["conflicts", "compliance_findings"]);

const SECTION_ICONS: Record<string, string> = {
  status_summary: "📈",
  milestones: "🎯",
  action_items: "✅",
  conflicts: "⚠",
  compliance_findings: "⚖",
};

function Line({ text, decisions }: { text: string; decisions: Map<string, string> }) {
  let body = text;
  let cites: string[] = [];

  const citeMatch = body.match(CITE_RE);
  if (citeMatch) {
    cites = citeMatch[1].split(",").map((c) => c.trim()).filter(Boolean);
    body = body.replace(CITE_RE, "").trim();
  }

  let tag: string | null = null;
  const tagMatch = body.match(TAG_RE);
  if (tagMatch) {
    tag = tagMatch[1];
    body = body.replace(TAG_RE, "").trim();
  }

  const statusMatch = body.match(STATUS_RE);
  const itemStatus = statusMatch ? statusMatch[1].toLowerCase() : null;
  if (statusMatch) body = body.replace(/,?\s*status\s+\w+/i, "").trim();

  const decision = decisions.get(norm(body));

  return (
    <li className={`reg-line ${tag ? "reg-line-flagged" : ""}`}>
      <div className="reg-line-main">
        {tag && (
          <span className={`reg-tag sev-${conflictMeta(tag).severity}`}>
            <span aria-hidden>{conflictMeta(tag).icon}</span> {conflictMeta(tag).label}
          </span>
        )}
        <span className="reg-line-text">{body}</span>
        {itemStatus && <span className={`chip chip-${itemStatus}`}>{itemStatus}</span>}
        {decision && <span className={`chip chip-${decision}`}>{decision}</span>}
      </div>
      {cites.length > 0 && (
        <div className="reg-cites">
          {cites.map((c) => (
            <span key={c} className="cite-pill mono">{c}</span>
          ))}
        </div>
      )}
    </li>
  );
}

function SectionBody({ content, decisions }: { content: string; decisions: Map<string, string> }) {
  const bullets = content
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"))
    .map((l) => l.replace(/^-\s*/, ""));

  if (bullets.length === 0 || (bullets.length === 1 && /^no /i.test(bullets[0]))) {
    return <p className="reg-empty">✓ {bullets[0] ?? "Nothing recorded in this section."}</p>;
  }
  return (
    <ul className="reg-lines">
      {bullets.map((b, i) => (
        <Line key={i} text={b} decisions={decisions} />
      ))}
    </ul>
  );
}

export function DeliverableView({
  sections,
  reviewItems = [],
}: {
  sections: DeliverableSection[];
  reviewItems?: PendingReviewItem[];
}) {
  if (sections.length === 0) {
    return <p className="empty-state">No register yet — run Understand first.</p>;
  }

  // Map a decided item's description → its status, so the register can show the
  // approve/reject decision the moment it's made (Dashboard re-fetches on approve).
  const decisions = new Map<string, string>();
  for (const it of reviewItems) {
    if (it.status !== "pending" && it.payload?.description) {
      decisions.set(norm(it.payload.description), it.status);
    }
  }

  return (
    <div className="register">
      {sections.map((s) => {
        const usesDecisions = REVIEWABLE_SECTIONS.has(s.section_key);
        return (
          <details key={s.section_key} open className="section-block">
            <summary>
              <span className="section-name">
                <span className="section-icon" aria-hidden>{SECTION_ICONS[s.section_key] ?? "▸"}</span>
                {sectionLabel(s.section_key)}
              </span>
              <span className="version-tag">v{s.version}</span>
            </summary>
            <div className="section-body">
              <SectionBody content={s.content} decisions={usesDecisions ? decisions : new Map()} />
            </div>
          </details>
        );
      })}
    </div>
  );
}
