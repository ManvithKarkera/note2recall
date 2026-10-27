import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { QuestionText, Source, Sparkle, letter, tone } from "./Source.jsx";

export default function Review({ cards, results, setResults }) {
  const [onlyAgain, setOnlyAgain] = useState(false);
  const [round, setRound] = useState(0);
  const order = useMemo(
    () => cards.map((_, i) => i).filter((i) => !onlyAgain || results[i] === "again"),
    // the queue is fixed when a round starts, not re-filtered on every grade
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [cards, onlyAgain, round]
  );
  const [pos, setPos] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const root = useRef(null);

  // on short screens, scroll so the card and its grade buttons are both in view
  useEffect(() => {
    function fit() {
      const buttons = root.current?.querySelector(".controls");
      if (buttons && buttons.getBoundingClientRect().bottom > window.innerHeight) {
        root.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [pos, flipped]);

  const finished = pos >= order.length;
  const idx = order[pos];
  const card = cards[idx];

  const go = useCallback((p) => { setPos(Math.max(0, Math.min(p, order.length))); setFlipped(false); }, [order.length]);
  const grade = useCallback((value) => {
    setResults((r) => ({ ...r, [idx]: value }));
    go(pos + 1);
  }, [idx, pos, go, setResults]);

  useEffect(() => {
    function onKey(e) {
      if (e.target.tagName === "INPUT" || finished) return;
      if (e.key === " ") { e.preventDefault(); setFlipped((f) => !f); }
      else if (e.key === "ArrowRight") go(pos + 1);
      else if (e.key === "ArrowLeft") go(pos - 1);
      else if (flipped && e.key === "1") grade("known");
      else if (flipped && e.key === "2") grade("again");
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pos, flipped, finished, go, grade]);

  const known = Object.values(results).filter((v) => v === "known").length;
  const again = Object.values(results).filter((v) => v === "again").length;
  const n = cards.length;

  function restart(againMode) {
    setOnlyAgain(againMode);
    setRound((r) => r + 1);
    setPos(0);
    setFlipped(false);
    if (!againMode) setResults({});
  }

  return (
    <div className="review" ref={root}>
      <div className="progress-row">
        <span>{onlyAgain ? "Repeating missed cards" : `Card ${Math.min(pos + 1, order.length)} of ${order.length}`}</span>
        <div className="bar" aria-hidden="true">
          <i className="k" style={{ width: `${(known / n) * 100}%` }} />
          <i className="a" style={{ width: `${(again / n) * 100}%` }} />
        </div>
        <span>{known} known · {again} again</span>
      </div>

      {finished ? (
        <div className="done-panel">
          <svg className="trophy" viewBox="0 0 84 84" aria-hidden="true">
            <rect x="10" y="18" width="34" height="46" rx="7" fill="var(--green)" transform="rotate(-14 27 41)" />
            <rect x="40" y="16" width="34" height="46" rx="7" fill="var(--blue)" transform="rotate(12 57 39)" />
            <rect x="24" y="12" width="36" height="50" rx="7" fill="var(--pink)" />
            <path d="M42 26l3.6 7.3 8 1.2-5.8 5.6 1.4 8-7.2-3.8-7.2 3.8 1.4-8-5.8-5.6 8-1.2z" fill="#fff" />
          </svg>
          <h3>{again === 0 ? "Deck complete!" : "Round complete!"}</h3>
          <p>You knew {known} of {n} cards{again ? `, and ${again} need another look` : ""}.</p>
          <div className="row">
            {again > 0 && <button className="btn btn-primary" onClick={() => restart(true)}>Repeat {again} missed card{again > 1 ? "s" : ""}</button>}
            <button className="btn" onClick={() => restart(false)}>Start over</button>
          </div>
        </div>
      ) : (
        <>
          <div className={`flip ${tone(idx)} ${flipped ? "flipped" : ""}`} onClick={() => setFlipped((f) => !f)}
               role="button" tabIndex={0} aria-label={flipped ? "Show question" : "Show answer"}>
            <div className="flip-inner">
              <div className="face" aria-hidden={flipped}>
                <Corners card={card} />
                <Sparkle style={{ top: "26%", right: "13%" }} />
                <Sparkle style={{ bottom: "24%", left: "11%", width: 16, height: 16 }} />
                <div className="face-body">
                  <span className="kind-tag">{card.kind === "definition" ? "Definition" : "Fill in the blank"}</span>
                  <p className={`question ${size(card.question)}`}><QuestionText card={card} /></p>
                </div>
                <div className="face-hint">Tap<span className="keys"> or press</span> <span className="kbd">Space</span> to flip</div>
              </div>
              <div className="face back" aria-hidden={!flipped}>
                <Corners card={card} />
                <div className="face-body">
                  {results[idx] && <span className={`badge ${results[idx]}`} style={{ marginBottom: 12 }}>{results[idx]}</span>}
                  <p className={`answer ${size(card.answer, 60, 140)}`}>{card.answer}</p>
                  <Source card={card} />
                </div>
              </div>
            </div>
          </div>

          <div className="controls">
            <div className="grade">
              <button className="btn btn-again" disabled={!flipped} onClick={() => grade("again")}>Again<span className="kbd">2</span></button>
              <button className="btn btn-good" disabled={!flipped} onClick={() => grade("known")}>Knew it<span className="kbd">1</span></button>
            </div>
            <div className="nav">
              <button className="btn btn-ghost" onClick={() => go(pos - 1)} disabled={pos === 0}>← Previous</button>
              <button className="btn btn-ghost" onClick={() => go(pos + 1)}>Skip →</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// a portrait card is narrow, so long text gets a smaller size instead of overflowing
function size(text, long = 70, xlong = 140) {
  return text.length > xlong ? "xlong" : text.length > long ? "long" : "";
}

function Corners({ card }) {
  const l = letter(card);
  return (
    <>
      <span className="corner tl" aria-hidden="true">{l}<small>p.{card.page}</small></span>
      <span className="corner br" aria-hidden="true">{l}<small>p.{card.page}</small></span>
    </>
  );
}
