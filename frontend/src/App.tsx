import { useEffect, useState } from "react";

type Health = { api: string; db: string };

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <main style={{ fontFamily: "sans-serif", padding: 24 }}>
      <h1>Central de Investimentos</h1>
      {error && <p>Erro: {error}</p>}
      {!health && !error && <p>Verificando…</p>}
      {health && (
        <ul>
          <li>API: {health.api}</li>
          <li>Banco: {health.db}</li>
        </ul>
      )}
    </main>
  );
}
