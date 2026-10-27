export async function createDeck(file, nCards, threshold) {
  const body = new FormData();
  body.append("file", file);
  body.append("n_cards", String(nCards));
  body.append("threshold", String(threshold));

  let res;
  try {
    res = await fetch("/api/deck", { method: "POST", body });
  } catch {
    throw new Error("Can't reach the note2recall server. Is it running? (uvicorn api:app --port 8000)");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Server error (${res.status})`);
  return data;
}

// Remember the last deck and review progress across page reloads (best effort)
const KEY = "smartnotes:last";
export const storage = {
  load() {
    try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
  },
  save(value) {
    try { localStorage.setItem(KEY, JSON.stringify(value)); } catch { /* storage unavailable */ }
  },
  clear() {
    try { localStorage.removeItem(KEY); } catch { /* storage unavailable */ }
  },
};
