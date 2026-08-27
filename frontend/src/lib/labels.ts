// Human-facing labels for the machine keys the backend emits. Keeping this in
// one place means the raw enums (status_vs_blocker, embedded_instruction_attempt,
// compliance_findings…) never leak into the UI as-is.

export type Severity = "high" | "medium" | "info";

interface CategoryMeta {
  label: string;
  icon: string;
  severity: Severity;
  blurb: string;
}

const CONFLICT_META: Record<string, CategoryMeta> = {
  status_vs_blocker: {
    label: "Status contradicts a blocker",
    icon: "⚠",
    severity: "high",
    blurb: "A status report claims progress while another doc records an open blocker for the same period.",
  },
  stalled_progress: {
    label: "Progress appears stalled",
    icon: "⏸",
    severity: "medium",
    blurb: "Percent-complete didn't move across reporting periods with no explanation.",
  },
  undocumented_scope_change: {
    label: "Undocumented scope change",
    icon: "📋",
    severity: "high",
    blurb: "A scope or date change has no approved change request behind it.",
  },
  stale_action_item: {
    label: "Stale action item",
    icon: "⌛",
    severity: "medium",
    blurb: "An action item stayed open across several meetings with no escalation.",
  },
  embedded_instruction_attempt: {
    label: "Injected instruction — ignored",
    icon: "🛡",
    severity: "info",
    blurb: "A source document tried to instruct the reviewer. It was treated as data, not obeyed.",
  },
};

const SECTION_LABELS: Record<string, string> = {
  status_summary: "Status summary",
  milestones: "Milestones",
  action_items: "Action items",
  conflicts: "Conflicts",
  compliance_findings: "Compliance findings",
};

export function conflictMeta(key: string | undefined): CategoryMeta {
  if (key && CONFLICT_META[key]) return CONFLICT_META[key];
  return { label: humanize(key ?? "conflict"), icon: "•", severity: "medium", blurb: "" };
}

export function sectionLabel(key: string): string {
  return SECTION_LABELS[key] ?? humanize(key);
}

// Turn snake_case / kebab-case into a readable Title-cased phrase as a fallback.
export function humanize(key: string): string {
  const spaced = key.replace(/[_-]+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
