import { useEffect, useState } from "react";
import { api, type DeliverableSection, type PendingReviewItem, type Rule } from "../api/client";
import { DeliverableView } from "../components/DeliverableView";
import { ReviewQueue } from "../components/ReviewQueue";

const STORAGE_KEY = "docdesk.activePile";
const PROVIDER_STORAGE_KEY = "docdesk.llmProvider";

interface StoredPile {
  id: string;
  name: string;
}

type LLMProvider = "fake" | "gemini" | "anthropic";

const PROVIDER_LABELS: Record<LLMProvider, string> = {
  fake: "Fake (free, deterministic)",
  gemini: "Gemini (real, free tier)",
  anthropic: "Anthropic (real, paid)",
};

function errMsg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

export function Dashboard() {
  const [pile, setPile] = useState<StoredPile | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as StoredPile) : null;
    } catch {
      // corrupt/unavailable localStorage must not white-screen the app on load
      return null;
    }
  });
  const [pileName, setPileName] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);
  const [uploadedCount, setUploadedCount] = useState(0);
  const [ruleText, setRuleText] = useState("");
  const [rules, setRules] = useState<Rule[]>([]);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [hasRun, setHasRun] = useState(false);
  const [reviewItems, setReviewItems] = useState<PendingReviewItem[]>([]);
  const [deliverable, setDeliverable] = useState<DeliverableSection[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [provider, setProvider] = useState<LLMProvider>(
    () => (localStorage.getItem(PROVIDER_STORAGE_KEY) as LLMProvider | null) ?? "fake"
  );

  function handleProviderChange(next: LLMProvider) {
    setProvider(next);
    localStorage.setItem(PROVIDER_STORAGE_KEY, next);
  }

  useEffect(() => {
    if (pile) refresh(pile.id).catch((e) => setStatus(`Failed to load pile: ${errMsg(e)}`));
  }, []);

  function persistPile(next: StoredPile | null) {
    setPile(next);
    if (next) localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    else localStorage.removeItem(STORAGE_KEY);
  }

  async function handleCreatePile() {
    if (!pileName.trim()) return;
    try {
      const created = await api.createPile(pileName.trim());
      persistPile({ id: created.id, name: created.name });
      setStatus(`Pile "${created.name}" created`);
    } catch (e) {
      setStatus(`Failed to create pile: ${errMsg(e)}`);
    }
  }

  function handleForgetPile() {
    persistPile(null);
    setUploadedCount(0);
    setHasRun(false);
    setReviewItems([]);
    setDeliverable([]);
    setRules([]);
    setStatus("");
  }

  async function handleUpload() {
    if (!pile || !files) return;
    const count = files.length;
    setBusy(true);
    setStatus(`Uploading ${count} document(s)...`);
    try {
      for (const file of Array.from(files)) {
        await api.uploadDocument(pile.id, file);
      }
      setUploadedCount((n) => n + count);
      setFiles(null);
      setStatus(`Uploaded ${count} document(s)`);
    } catch (e) {
      setStatus(`Upload failed: ${errMsg(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function refresh(pileId: string) {
    const [items, sections, currentRules] = await Promise.all([
      api.listReview(pileId),
      api.getDeliverable(pileId),
      api.listRules(pileId),
    ]);
    setReviewItems(items);
    setDeliverable(sections);
    setRules(currentRules);
    if (sections.length > 0) setHasRun(true);
  }

  async function handleStartRun() {
    if (!pile) return;
    setBusy(true);
    setStatus(`Running Movement 1 (understand) via ${PROVIDER_LABELS[provider]}...`);
    try {
      const run = await api.startRun(pile.id, provider);
      setHasRun(true);
      setStatus(`Run ${run.status}`);
      await refresh(pile.id);
    } catch (e) {
      setStatus(`Run failed: ${errMsg(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleAddRule() {
    if (!pile || !ruleText.trim()) return;
    try {
      await api.submitRule(pile.id, ruleText.trim());
      setRuleText("");
      await refresh(pile.id);
    } catch (e) {
      setStatus(`Failed to add rule: ${errMsg(e)}`);
    }
  }

  async function handleStartExamine() {
    if (!pile) return;
    setBusy(true);
    setStatus(`Running Movement 2 (examine) via ${PROVIDER_LABELS[provider]}...`);
    try {
      const run = await api.startExamine(pile.id, provider);
      setStatus(`Examine ${run.status}`);
      await refresh(pile.id);
    } catch (e) {
      setStatus(`Examine failed: ${errMsg(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(itemId: string) {
    if (!pile) return;
    setBusyId(itemId);
    try {
      await api.approve(itemId, "mohit");
      await refresh(pile.id);
    } catch (e) {
      setStatus(`Approve failed: ${errMsg(e)}`);
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(itemId: string) {
    if (!pile) return;
    setBusyId(itemId);
    try {
      await api.reject(itemId, "mohit");
      await refresh(pile.id);
    } catch (e) {
      setStatus(`Reject failed: ${errMsg(e)}`);
    } finally {
      setBusyId(null);
    }
  }

  const steps = [
    { label: "Pile", done: !!pile },
    { label: "Documents", done: uploadedCount > 0 },
    { label: "Understand", done: hasRun },
    { label: "Rules & Examine", done: rules.length > 0 },
    { label: "Review", done: reviewItems.length > 0 && reviewItems.every((i) => i.status !== "pending") },
    { label: "Register", done: deliverable.length > 0 },
  ];
  const activeIndex = steps.findIndex((s) => !s.done);

  return (
    <main className="app">
      <div className="app-header">
        <h1>Document Health Register</h1>
        <p>An agentic system that understands, examines, and stays current on a pile of project documents.</p>
      </div>

      <div className="row provider-select">
        <label htmlFor="llm-provider">LLM provider</label>
        <select
          id="llm-provider"
          className="input"
          value={provider}
          onChange={(e) => handleProviderChange(e.target.value as LLMProvider)}
        >
          {(Object.keys(PROVIDER_LABELS) as LLMProvider[]).map((p) => (
            <option key={p} value={p}>
              {PROVIDER_LABELS[p]}
            </option>
          ))}
        </select>
      </div>

      <div className="stepper">
        {steps.map((s, i) => (
          <div key={s.label} className={`step ${s.done ? "done" : i === activeIndex ? "active" : ""}`}>
            <span className="step-num">{s.done ? "✓" : i + 1}</span>
            {s.label}
          </div>
        ))}
      </div>

      <section className="card">
        <div className="card-title">
          <span className="step-num">1</span> Pile
        </div>
        {pile ? (
          <div className="pile-identity">
            <span className="pile-name">{pile.name}</span>
            <span className="pile-id mono">{pile.id}</span>
            <button className="btn btn-ghost" onClick={handleForgetPile} style={{ marginLeft: "auto" }}>
              Switch pile
            </button>
          </div>
        ) : (
          <div className="row">
            <input
              className="input"
              placeholder="Pile name (e.g. atlas-migration)"
              value={pileName}
              onChange={(e) => setPileName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreatePile()}
            />
            <button className="btn btn-primary" onClick={handleCreatePile}>
              Create pile
            </button>
          </div>
        )}
      </section>

      {pile && (
        <>
          <section className="card">
            <div className="card-title">
              <span className="step-num">2</span> Documents
              {uploadedCount > 0 && <span className="card-title-sub">{uploadedCount} uploaded this session</span>}
            </div>
            <div className="row">
              <div className="file-picker">
                <span className="file-picker-label">
                  {files ? `${files.length} file(s) selected` : "Choose files..."}
                </span>
                <input type="file" multiple onChange={(e) => setFiles(e.target.files)} />
              </div>
              <button className="btn btn-primary" onClick={handleUpload} disabled={!files || busy}>
                Upload
              </button>
            </div>
          </section>

          <section className="card">
            <div className="card-title">
              <span className="step-num">3</span> Understand
              <span className="card-title-sub">Movement 1 — ingest, classify, extract facts, detect conflicts</span>
            </div>
            <div className="row">
              <button className="btn btn-primary" onClick={handleStartRun} disabled={busy}>
                Start run
              </button>
              <button className="btn" onClick={() => refresh(pile.id)}>
                Refresh
              </button>
            </div>
          </section>

          <section className="card">
            <div className="card-title">
              <span className="step-num">4</span> Rules &amp; Examine
              <span className="card-title-sub">Movement 2 — check the pile against your governance rules</span>
            </div>
            <div className="row" style={{ marginBottom: rules.length > 0 ? "0.75rem" : 0 }}>
              <input
                className="input"
                placeholder="e.g. No status report may say on track while an open blocker exists..."
                value={ruleText}
                onChange={(e) => setRuleText(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAddRule()}
              />
              <button className="btn" onClick={handleAddRule}>
                Add rule
              </button>
            </div>
            {rules.length > 0 && (
              <ul className="rules-list">
                {rules.map((r) => (
                  <li key={r.id}>{r.rule_text}</li>
                ))}
              </ul>
            )}
            <button className="btn btn-primary" onClick={handleStartExamine} disabled={busy || rules.length === 0}>
              Start examine
            </button>
          </section>

          <section className="card">
            <div className="card-title">
              <span className="step-num">5</span> Review queue
              {reviewItems.length > 0 && (
                <span className="card-title-sub">
                  {reviewItems.filter((i) => i.status === "pending").length} pending
                </span>
              )}
            </div>
            <ReviewQueue items={reviewItems} onApprove={handleApprove} onReject={handleReject} busyId={busyId} />
          </section>

          <section className="card">
            <div className="card-title">
              <span className="step-num">6</span> Project Health Register
            </div>
            <DeliverableView sections={deliverable} />
          </section>
        </>
      )}

      {status && (
        <div className="status-toast">
          <span className={`status-dot ${busy ? "busy" : ""}`} />
          {status}
        </div>
      )}
    </main>
  );
}
