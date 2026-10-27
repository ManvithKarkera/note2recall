import { useEffect, useState } from "react";
import { createDeck, storage } from "./api.js";
import Upload from "./components/Upload.jsx";
import Loading from "./components/Loading.jsx";
import Review from "./components/Review.jsx";
import CardList from "./components/CardList.jsx";
import Quiz from "./components/Quiz.jsx";
import Insights from "./components/Insights.jsx";

const TABS = [
  { id: "review", label: "Review" },
  { id: "cards", label: "All cards" },
  { id: "quiz", label: "Quiz" },
  { id: "insights", label: "Insights" },
];

export default function App() {
  const [saved] = useState(() => storage.load());
  const [deck, setDeck] = useState(saved?.deck ?? null);
  const [results, setResults] = useState(saved?.results ?? {});   // card index -> "known" | "again"
  const [tab, setTab] = useState("review");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (deck) storage.save({ deck, results });
  }, [deck, results]);

  async function generate(file, nCards, threshold) {
    setError("");
    setLoading(true);
    try {
      const d = await createDeck(file, nCards, threshold);
      setDeck(d);
      setResults({});
      setTab("review");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    storage.clear();
    setDeck(null);
    setResults({});
    setError("");
  }

  const cloze = deck ? deck.cards.filter((c) => c.kind === "cloze").length : 0;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <svg className="brand-mark" viewBox="0 0 42 42" aria-hidden="true">
            <rect x="4" y="9" width="20" height="28" rx="5" fill="var(--green)" transform="rotate(-12 14 23)" />
            <rect x="11" y="6" width="20" height="28" rx="5" fill="var(--blue)" transform="rotate(-2 21 20)" />
            <rect x="18" y="7" width="20" height="28" rx="5" fill="var(--pink)" transform="rotate(10 28 21)" />
            <text x="28" y="26" textAnchor="middle" fill="#fff" fontFamily="Fredoka, sans-serif" fontWeight="700" fontSize="14" transform="rotate(10 28 21)">n</text>
          </svg>
          <div>
            <h1>note<span className="two">2</span>recall</h1>
            <small>From notes to active recall</small>
          </div>
        </div>
        {deck && !loading && (
          <div className="file-pill">
            <span>Deck from</span>
            <strong title={deck.filename}>{deck.filename}</strong>
            <button className="btn" onClick={reset}>New upload</button>
          </div>
        )}
      </header>

      {loading && <Loading />}
      {!loading && !deck && <Upload onGenerate={generate} error={error} />}

      {!loading && deck && (
        <main>
          <section className="stats" aria-label="Deck summary">
            <Stat value={deck.stats.cards} label="flashcards" />
            <Stat value={deck.stats.sentences} label="sentences analysed" />
            <Stat value={deck.duplicates.length} label="duplicates removed" />
            <Stat value={`${Math.round(deck.coverage.ratio * 100)}%`} label="key concepts covered" />
          </section>

          <nav className="tabs" role="tablist">
            {TABS.map((t) => (
              <button key={t.id} role="tab" className="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}>
                {t.label}
                {t.id === "cards" && <span className="count">{deck.cards.length}</span>}
                {t.id === "quiz" && <span className="count">{cloze}</span>}
              </button>
            ))}
          </nav>

          {tab === "review" && <Review cards={deck.cards} results={results} setResults={setResults} />}
          {tab === "cards" && <CardList cards={deck.cards} results={results} />}
          {tab === "quiz" && <Quiz cards={deck.cards} />}
          {tab === "insights" && <Insights deck={deck} />}
        </main>
      )}
    </div>
  );
}

function Stat({ value, label }) {
  return (
    <div className="stat">
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}
