import type { PendingReviewItem } from "../api/client";
import { ConflictCard } from "./ConflictCard";

interface Props {
  items: PendingReviewItem[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  busyId: string | null;
}

export function ReviewQueue({ items, onApprove, onReject, busyId }: Props) {
  if (items.length === 0) {
    return <p>No review items yet — start a run against some documents first.</p>;
  }
  return (
    <div>
      {items.map((item) => (
        <ConflictCard
          key={item.id}
          item={item}
          busy={busyId === item.id}
          onApprove={() => onApprove(item.id)}
          onReject={() => onReject(item.id)}
        />
      ))}
    </div>
  );
}
