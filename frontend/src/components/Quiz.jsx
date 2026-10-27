import { useMemo, useState } from "react";
import { QuestionText, tone } from "./Source.jsx";

function shuffle(arr, rand) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// small seeded RNG so a quiz round stays stable across re-renders
function rng(seed) {
  return () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
}

// Distractors: answers of the other cloze cards, preferring ones of the same "shape"
// (acronym vs phrase, similar length) so the right answer doesn't stand out.
function buildQuestions(cloze, seed) {
  const rand = rng(seed);
  const answers = [...new Map(cloze.map((c) => [c.answer.toLowerCase(), c.answer])).values()];
  const shape = (a) => `${a === a.toUpperCase()}-${a.split(" ").length > 1}`;
  return shuffle(cloze, rand).map((c) => {
    const others = answers.filter((a) => a.toLowerCase() !== c.answer.toLowerCase());
    const same = shuffle(others.filter((a) => shape(a) === shape(c.answer)), rand);
    const rest = shuffle(others.filter((a) => shape(a) !== shape(c.answer)), rand);
    return { card: c, options: shuffle([c.answer, ...[...same, ...rest].slice(0, 3)], rand) };
  });
}

export default function Quiz({ cards }) {
  const cloze = cards.filter((c) => c.kind === "cloze");
  const [seed, setSeed] = useState(7);
  const [picked, setPicked] = useState({});
  const questions = useMemo(() => buildQuestions(cloze, seed), [cards, seed]); // eslint-disable-line react-hooks/exhaustive-deps

  if (cloze.length < 4) {
    return <div className="empty">A quiz needs at least 4 fill-in-the-blank cards. Try generating more cards.</div>;
  }

  const answered = Object.keys(picked).length;
  const score = questions.filter((q, i) => picked[i] === q.card.answer).length;

  return (
    <div className="quiz">
      <div className="quiz-head">
        <h3>Score {score} / {answered}{answered < questions.length && <span className="left"> · {questions.length - answered} left</span>}</h3>
        <button className="btn" onClick={() => { setSeed((s) => s + 1); setPicked({}); }}>New quiz</button>
      </div>
      {questions.map((q, i) => {
        const choice = picked[i];
        return (
          <div className={`q ${tone(i)}`} key={`${seed}-${i}`}>
            <p><span className="n">{i + 1}</span><QuestionText card={q.card} /></p>
            <div className="opts">
              {q.options.map((o) => {
                const cls = choice === undefined ? "" : o === q.card.answer ? "correct" : o === choice ? "wrong" : "";
                return (
                  <button key={o} className={`opt ${cls}`} disabled={choice !== undefined}
                          onClick={() => setPicked((p) => ({ ...p, [i]: o }))}>{o}</button>
                );
              })}
            </div>
            {choice !== undefined && choice !== q.card.answer && (
              <div className="why">Answer: <b>{q.card.answer}</b> (page {q.card.page})</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
