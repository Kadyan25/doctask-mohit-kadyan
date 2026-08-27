import type { PendingReviewItem } from "../api/client";
import { conflictMeta } from "../lib/labels";

interface Props {
  item: PendingReviewItem;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}

export function ConflictCard({ item, onApprove, onReject, busy }: Props) {
  const { description, citations, conflict_type, rule_text } = item.payload;
  const isFinding = item.item_type === "finding";

  // Findings come from a user rule; conflicts come from a detector category.
  const meta = isFinding
    ? { label: "Rule violation", icon: "⚖", severity: "high" as const }
    : conflictMeta(conflict_type);

  return (
    <div className={`finding-card sev-${meta.severity} ${item.status !== "pending" ? "is-decided" : ""}`}>
      <div className="finding-head">
        <span className="finding-icon" aria-hidden>{meta.icon}</span>
        <div className="finding-titles">
          <span className="finding-title">{meta.label}</span>
          <span className="finding-kind">{isFinding ? "Finding · from your rule" : "Conflict · auto-detected"}</span>
        </div>
        <span className={`sev-tag sev-${meta.severity}`}>{meta.severity}</span>
      </div>

      {isFinding && rule_text && <div className="finding-rule">“{rule_text}”</div>}

      <p className="finding-desc">{description}</p>

      {citations?.length > 0 && (
        <div className="finding-citations">
          <span className="finding-citations-label">Evidence</span>
          {citations.map((c) => (
            <span key={c} className="cite-pill mono">{c}</span>
          ))}
        </div>
      )}

      {item.status === "pending" ? (
        <div className="finding-actions">
          <button className="btn btn-success" disabled={busy} onClick={onApprove}>
            Approve
          </button>
          <button className="btn btn-danger" disabled={busy} onClick={onReject}>
            Reject
          </button>
        </div>
      ) : (
        <div className="finding-decided">
          <span className={`badge badge-status-${item.status}`}>{item.status}</span>
          {item.reviewer && <span className="finding-decided-by">by {item.reviewer}</span>}
        </div>
      )}
    </div>
  );
}
