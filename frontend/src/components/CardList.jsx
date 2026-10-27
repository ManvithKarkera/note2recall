import { useState } from "react";
import { KindBadge, Source, letter, tone } from "./Source.jsx";

export default function CardList({ cards, results }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");

  const q = query.trim().toLowerCase();
  const shown = cards
    .map((c, i) => ({ ...c, i }))
    .filter((c) => kind === "all" || c.kind === kind)
    .filter((c) => !q || `${c.question} ${c.answer} ${c.keyword}`.toLowerCase().includes(q));

  return (
    <>
      <div className="toolbar">
        <input className="search" type="search" placeholder="Search questions, answers, concepts…"
               value={query} onChange={(e) => setQuery(e.target.value)} />
        <div className="seg" role="group" aria-label="Card type">
          {[["all", "All"], ["definition", "Definitions"], ["cloze", "Fill in the blank"]].map(([v, l]) => (
            <button key={v} aria-pressed={kind === v} onClick={() => setKind(v)}>{l}</button>
          ))}
        </div>
      </div>

      <div className="list">
        {shown.length === 0 && <div className="empty">No cards match.</div>}
        {shown.map((c) => (
          <article className={`item ${tone(c.i)}`} key={c.i}>
            <span className="letter" aria-hidden="true">{letter(c)}</span>
            <div className="item-head">
              <h4>{c.question}</h4>
              <KindBadge kind={c.kind} />
            </div>
            <p className="a">{c.answer}</p>
            <Source card={c} />
            <div className="meta">
              Concept: {c.keyword} · score {c.score.toFixed(2)}
              {results[c.i] && <> · <span className={`badge ${results[c.i]}`}>{results[c.i]}</span></>}
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
