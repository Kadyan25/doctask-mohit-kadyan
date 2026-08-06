import { useState } from "react";
import { api, type DeliverableSection, type PendingReviewItem } from "../api/client";
import { DeliverableView } from "../components/DeliverableView";
import { ReviewQueue } from "../components/ReviewQueue";

export function Dashboard() {
  const [pileId, setPileId] = useState<string | null>(null);
  const [pileName, setPileName] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [status, setStatus] = useState("");
  const [reviewItems, setReviewItems] = useState<PendingReviewItem[]>([]);
  const [deliverable, setDeliverable] = useState<DeliverableSection[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function handleCreatePile() {
    if (!pileName.trim()) return;
    const pile = await api.createPile(pileName.trim());
    setPileId(pile.id);
    setStatus(`Pile created: ${pile.id}`);
  }

  async function handleUpload() {
    if (!pileId || !files) return;
    setStatus("Uploading...");
    for (const file of Array.from(files)) {
      await api.uploadDocument(pileId, file);
    }
    setStatus(`Uploaded ${files.length} document(s)`);
  }

  async function refresh(currentPileId: string) {
    const [items, sections] = await Promise.all([
      api.listReview(currentPileId),
      api.getDeliverable(currentPileId),
    ]);
    setReviewItems(items);
    setDeliverable(sections);
  }

  async function handleStartRun() {
    if (!pileId) return;
    setStatus("Running pipeline...");
    const run = await api.startRun(pileId);
    setStatus(`Run ${run.status}`);
    await refresh(pileId);
  }

  async function handleApprove(itemId: string) {
    if (!pileId) return;
    setBusyId(itemId);
    await api.approve(itemId, "mohit");
    await refresh(pileId);
    setBusyId(null);
  }

  async function handleReject(itemId: string) {
    if (!pileId) return;
    setBusyId(itemId);
    await api.reject(itemId, "mohit");
    await refresh(pileId);
    setBusyId(null);
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 900, margin: "0 auto" }}>
      <h1>Document Health Register</h1>

      <section style={{ marginBottom: "1.5rem" }}>
        <h2>1. Pile</h2>
        {pileId ? (
          <p>
            Active pile: <code>{pileId}</code>
          </p>
        ) : (
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <input
              placeholder="Pile name (e.g. atlas-migration)"
              value={pileName}
              onChange={(e) => setPileName(e.target.value)}
            />
            <button onClick={handleCreatePile}>Create pile</button>
          </div>
        )}
      </section>

      {pileId && (
        <>
          <section style={{ marginBottom: "1.5rem" }}>
            <h2>2. Documents</h2>
            <input type="file" multiple onChange={(e) => setFiles(e.target.files)} />
            <button onClick={handleUpload} disabled={!files}>
              Upload
            </button>
          </section>

          <section style={{ marginBottom: "1.5rem" }}>
            <h2>3. Run</h2>
            <button onClick={handleStartRun}>Start run</button>
            <button onClick={() => refresh(pileId)} style={{ marginLeft: "0.5rem" }}>
              Refresh
            </button>
          </section>

          <section style={{ marginBottom: "1.5rem" }}>
            <h2>4. Review queue</h2>
            <ReviewQueue items={reviewItems} onApprove={handleApprove} onReject={handleReject} busyId={busyId} />
          </section>

          <section>
            <h2>5. Project Health Register</h2>
            <DeliverableView sections={deliverable} />
          </section>
        </>
      )}

      {status && <p style={{ color: "#666", fontSize: "0.85rem" }}>{status}</p>}
    </main>
  );
}
