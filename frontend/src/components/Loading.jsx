import { useEffect, useState } from "react";

// The API answers in one response, so these steps are paced on a timer to show
// what the pipeline is doing; the last step stays active until the deck arrives.
const STEPS = [
  "Extracting text from the document",
  "Cleaning and splitting sentences",
  "Extracting key concepts with TF-IDF",
  "Ranking the most informative sentences",
  "Generating questions and answers",
  "Removing duplicates with sentence embeddings",
];

export default function Loading() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 900);
    return () => clearInterval(id);
  }, []);

  return (
    <section className="loading" aria-live="polite">
      <div className="shuffle" aria-hidden="true"><span /><span /><span /><span /></div>
      <h2>Shuffling your deck…</h2>
      <ol className="steps">
        {STEPS.map((s, i) => (
          <li key={s} className={i < step ? "done" : i === step ? "active" : ""}>
            <span className="dot" />
            {s}
          </li>
        ))}
      </ol>
    </section>
  );
}
