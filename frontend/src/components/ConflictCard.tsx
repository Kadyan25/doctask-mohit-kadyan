import type { PendingReviewItem } from "../api/client";

interface Props {
  item: PendingReviewItem;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}

export function ConflictCard({ item, onApprove, onReject, busy }: Props) {
  const { description, citations, conflict_type, rule_text } = item.payload;
  const label = conflict_type ?? (rule_text ? `finding: ${rule_text.slice(0, 60)}...` : item.item_type);
  return (
    <div style={{ border: "1px solid #ccc", borderRadius: 8, padding: "0.75rem 1rem", marginBottom: "0.75rem" }}>
      <div style={{ fontSize: "0.75rem", textTransform: "uppercase", color: "#888" }}>{label}</div>
      <p style={{ margin: "0.25rem 0" }}>{description}</p>
      <div style={{ fontSize: "0.75rem", color: "#666" }}>Citations: {citations?.join(", ")}</div>
      {item.status === "pending" ? (
        <div style={{ marginTop: "0.5rem", display: "flex", gap: "0.5rem" }}>
          <button disabled={busy} onClick={onApprove}>
            Approve
          </button>
          <button disabled={busy} onClick={onReject}>
            Reject
          </button>
        </div>
      ) : (
        <div style={{ marginTop: "0.5rem", fontWeight: 600 }}>
          {item.status} {item.reviewer ? `by ${item.reviewer}` : ""}
        </div>
      )}
    </div>
  );
}
