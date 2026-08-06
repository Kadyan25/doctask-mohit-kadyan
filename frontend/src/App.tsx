import { useEffect, useState } from "react";

type BackendStatus = "checking" | "ok" | "unreachable";

function App() {
  const [health, setHealth] = useState<BackendStatus>("checking");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => setHealth(res.ok ? "ok" : "unreachable"))
      .catch(() => setHealth("unreachable"));
  }, []);

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", padding: "2rem", maxWidth: 640 }}>
      <h1>Document Health Register</h1>
      <p>Phase 0 scaffold. The review queue (conflicts, findings, updates) lands here in Phase 1.</p>
      <p>
        Backend: <strong>{health}</strong>
      </p>
    </main>
  );
}

export default App;
