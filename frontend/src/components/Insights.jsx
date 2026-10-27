export default function Insights({ deck }) {
  const { coverage, keywords, duplicates, top_sentences, stats } = deck;
  const covered = new Set(coverage.covered);
  const pct = Math.round(coverage.ratio * 100);
  const r = 34, circ = 2 * Math.PI * r;

  return (
    <div className="grid-2">
      <section className="panel">
        <h3>Concept coverage</h3>
        <p className="sub">Top concepts from TF-IDF over noun phrases, and whether any card tests them.</p>
        <div className="meter">
          <svg viewBox="0 0 84 84" role="img" aria-label={`${pct}% of key concepts covered`}>
            <circle cx="42" cy="42" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="11" />
            <circle cx="42" cy="42" r={r} fill="none" stroke="var(--green)" strokeWidth="11" strokeLinecap="round"
                    strokeDasharray={`${(pct / 100) * circ} ${circ}`} transform="rotate(-90 42 42)" />
          </svg>
          <div>
            <b>{pct}%</b>
            <div style={{ color: "var(--ink-3)", fontSize: 13 }}>
              {coverage.covered.length} of {keywords.length} concepts covered
            </div>
          </div>
        </div>
        <div className="chips">
          {keywords.map(({ keyword }) => (
            <span key={keyword} className={`chip ${covered.has(keyword) ? "ok" : "miss"}`}>
              {covered.has(keyword) ? "✓ " : "+ "}{keyword}
            </span>
          ))}
        </div>
      </section>

      <section className="panel">
        <h3>Not in your deck yet</h3>
        <p className="sub">Important concepts that no card tests. Write cards for these, or generate a bigger deck.</p>
        {coverage.missing.length === 0
          ? <p>Every key concept is tested by at least one card.</p>
          : <div className="chips">{coverage.missing.map((k) => <span key={k} className="chip miss">{k}</span>)}</div>}

        <h3 style={{ marginTop: 22 }}>Duplicates removed</h3>
        <p className="sub">Compared with {stats.similarity_method === "tfidf" ? "TF-IDF" : "sentence embeddings (MiniLM)"} and an acronym-aware concept match.</p>
        {duplicates.length === 0 && <p style={{ color: "var(--ink-3)" }}>None found.</p>}
        {duplicates.map((d, i) => (
          <div className="dup" key={i}>
            <div className="why">
              <span className={`badge ${d.reason === "same concept" ? "cloze" : "def"}`}>{d.reason}</span>
              similarity {d.similarity.toFixed(2)}
            </div>
            <div className="s dropped"><b>Dropped</b>{d.dropped.question}</div>
            <div className="s"><b>Kept</b>{d.kept.question}</div>
          </div>
        ))}
      </section>

      <section className="panel full">
        <h3>Most informative sentences</h3>
        <p className="sub">Score = mean TF-IDF weight + a bonus for each key concept the sentence mentions.</p>
        <table>
          <thead><tr><th>Score</th><th>Page</th><th>Sentence</th></tr></thead>
          <tbody>
            {top_sentences.map((s, i) => (
              <tr key={i}><td className="num">{s.score.toFixed(2)}</td><td className="num">{s.page}</td><td>{s.text}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
