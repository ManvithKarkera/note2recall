import { useRef, useState } from "react";
import { Sparkle } from "./Source.jsx";

// decorative study doodles for the cards floating around the upload box
const BOOK = (
  <>
    <path d="M6 14c6-3 12-3 18 1v24c-6-4-12-4-18-1z" fill="#fff" />
    <path d="M42 14c-6-3-12-3-18 1v24c6-4 12-4 18-1z" fill="#fff" opacity=".8" />
    <path d="M10 20c3-1 7-1 10 1M10 26c3-1 7-1 10 1M28 21c3-2 7-2 10-1" stroke="var(--green)" strokeWidth="2" strokeLinecap="round" />
  </>
);
const BULB = (
  <>
    <path d="M24 6a13 13 0 0 0-8 23c2 2 3 4 3 6h10c0-2 1-4 3-6A13 13 0 0 0 24 6z" fill="#fff" />
    <rect x="19" y="37" width="10" height="5" rx="2" fill="var(--orange-ink)" />
    <path d="M24 16v8M20 20l4 4 4-4" stroke="var(--orange)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
  </>
);
const PENCIL = (
  <>
    <path d="M12 36l3-10 19-19 7 7-19 19z" fill="#fff" />
    <path d="M12 36l3-10 7 7z" fill="#ffd84d" />
    <path d="M30 11l7 7" stroke="var(--blue)" strokeWidth="3" />
  </>
);
const STAR = (
  <path d="M24 6l5.5 11.2 12.3 1.8-8.9 8.7 2.1 12.3L24 34.2 13 40l2.1-12.3-8.9-8.7 12.3-1.8z" fill="#fff" />
);
const FLOATERS = [["f1", "B", BOOK], ["f2", "L", BULB], ["f3", "P", PENCIL], ["f4", "S", STAR]];

export default function Upload({ onGenerate, error }) {
  const [file, setFile] = useState(null);
  const [over, setOver] = useState(false);
  const [nCards, setNCards] = useState(15);
  const [threshold, setThreshold] = useState(0.8);
  const input = useRef(null);

  function pick(f) {
    if (f && /\.(pdf|txt)$/i.test(f.name)) setFile(f);
  }

  return (
    <>
      <section className="hero">
        <h2>Turn your notes into <em>flashcards</em> you can actually revise from.</h2>
        <p>Upload a lecture PDF. Every card is built from your own notes and links back to the sentence and page it came from.</p>
      </section>

      <div className="table">
      <div className="floaters" aria-hidden="true">
        {FLOATERS.map(([cls, l, d]) => (
          <div key={cls} className={`floater ${cls}`}>
            <span>{l}</span>
            <svg className="doodle" viewBox="0 0 48 48">{d}</svg>
            <Sparkle style={{ top: 12, right: 12, width: 14, height: 14 }} />
            <span className="br">{l}</span>
          </div>
        ))}
      </div>
      <section className="upload-card">
        <div
          className={`dropzone ${over ? "over" : ""} ${file ? "has-file" : ""}`}
          role="button"
          tabIndex={0}
          onClick={() => input.current.click()}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current.click()}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}
        >
          <svg className="icon" viewBox="0 0 64 64" aria-hidden="true">
            <rect x="8" y="14" width="26" height="36" rx="6" fill="var(--green)" transform="rotate(-14 21 32)" />
            <rect x="30" y="12" width="26" height="36" rx="6" fill="var(--blue)" transform="rotate(12 43 30)" />
            <rect x="19" y="10" width="26" height="38" rx="6" fill="var(--pink)" />
            <path d="M32 38V22M25 28l7-7 7 7" stroke="#fff" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
          </svg>
          {file ? (
            <>
              <strong>{file.name}</strong>
              <span>{(file.size / 1024 / 1024).toFixed(2)} MB · click to choose a different file</span>
            </>
          ) : (
            <>
              <strong>Drop a PDF or TXT here</strong>
              <span>or click to browse · scanned PDFs are read with OCR</span>
            </>
          )}
          <input ref={input} type="file" accept=".pdf,.txt" hidden onChange={(e) => pick(e.target.files[0])} />
        </div>

        <div className="options">
          <div className="field">
            <label htmlFor="n">Number of cards <output>{nCards}</output></label>
            <input id="n" type="range" min="5" max="40" value={nCards} onChange={(e) => setNCards(+e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="t">Duplicate threshold <output>{threshold.toFixed(2)}</output></label>
            <input id="t" type="range" min="0.5" max="0.95" step="0.05" value={threshold}
                   onChange={(e) => setThreshold(+e.target.value)} />
            <p>Cards whose sentences are more similar than this are merged.</p>
          </div>
        </div>

        <button className="btn btn-primary" disabled={!file} onClick={() => onGenerate(file, nCards, threshold)}>
          Generate flashcards
        </button>
        {error && <div className="alert" role="alert">{error}</div>}
      </section>
      </div>

      <section className="how" aria-label="How it works">
        <div><i>1</i><b>Clean the text</b><span>Fixes PDF and slide artefacts, then splits the text into sentences.</span></div>
        <div><i>2</i><b>Find key concepts</b><span>TF-IDF over noun phrases, weighted by how specialised each term is.</span></div>
        <div><i>3</i><b>Write questions</b><span>Definitions become "What is…?" cards. Key terms become fill-in-the-blanks.</span></div>
        <div><i>4</i><b>Check the deck</b><span>Sentence embeddings remove duplicates, and the deck shows which concepts it missed.</span></div>
      </section>
    </>
  );
}
