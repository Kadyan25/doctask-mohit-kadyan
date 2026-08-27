import type { PendingReviewItem } from "../api/client";
import { conflictMeta, type Severity } from "../lib/labels";
import { ConflictCard } from "./ConflictCard";

interface Props {
  items: PendingReviewItem[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  busyId: string | null;
}

function severityOf(item: PendingReviewItem): Severity {
  if (item.item_type === "finding") return "high";
  return conflictMeta(item.payload?.conflict_type).severity;
}

const SEV_LABEL: Record<Severity, string> = { high: "high", medium: "medium", info: "handled" };

export function ReviewQueue({ items, onApprove, onReject, busyId }: Props) {
  if (items.length === 0) {
    return <p className="empty-state">No review items yet — run Understand (or Examine) against your documents first.</p>;
  }

  const pending = items.filter((i) => i.status === "pending");
  const decided = items.filter((i) => i.status !== "pending");

  const counts: Record<Severity, number> = { high: 0, medium: 0, info: 0 };
  pending.forEach((i) => (counts[severityOf(i)] += 1));

  return (
    <div className="review">
      {pending.length > 0 && (
        <div className="sev-summary">
          {(["high", "medium", "info"] as Severity[])
            .filter((s) => counts[s] > 0)
            .map((s) => (
              <span key={s} className={`sev-chip sev-${s}`}>
                <span className="sev-dot" />
                {counts[s]} {SEV_LABEL[s]}
              </span>
            ))}
          <span className="sev-summary-total">{pending.length} awaiting your decision</span>
        </div>
      )}

      {pending.length > 0 && (
        <div className="review-group">
          <div className="review-group-head">
            <span className="review-group-title">Needs your review</span>
          </div>
          {pending.map((item) => (
            <ConflictCard
              key={item.id}
              item={item}
              busy={busyId === item.id}
              onApprove={() => onApprove(item.id)}
              onReject={() => onReject(item.id)}
            />
          ))}
        </div>
      )}

      {decided.length > 0 && (
        <div className="review-group">
          <div className="review-group-head">
            <span className="review-group-title">Reviewed</span>
            <span className="review-group-count">{decided.length} decided</span>
          </div>
          {decided.map((item) => (
            <ConflictCard
              key={item.id}
              item={item}
              busy={busyId === item.id}
              onApprove={() => onApprove(item.id)}
              onReject={() => onReject(item.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
