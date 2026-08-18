import type { PendingReviewItem } from "../api/client";

interface Props {
  item: PendingReviewItem;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}

export function ConflictCard({ item, onApprove, onReject, busy }: Props) {
  const { description, citations, conflict_type, rule_text } = item.payload;
  const isFinding = item.item_type === "finding";
  const label = conflict_type ?? (rule_text ? rule_text : item.item_type);

  return (
    <div className="queue-item">
      <span className={`badge ${isFinding ? "badge-finding" : "badge-conflict"}`}>{label}</span>
      <p className="queue-item-desc">{description}</p>
      {citations?.length > 0 && <div className="queue-item-citations">Citations: {citations.join(", ")}</div>}
      {item.status === "pending" ? (
        <div className="queue-item-actions">
          <button className="btn btn-success" disabled={busy} onClick={onApprove}>
            Approve
          </button>
          <button className="btn btn-danger" disabled={busy} onClick={onReject}>
            Reject
          </button>
        </div>
      ) : (
        <div className="queue-item-decided">
          <span className={`badge badge-status-${item.status}`}>{item.status}</span>
          {item.reviewer && <span>by {item.reviewer}</span>}
        </div>
      )}
    </div>
  );
}
