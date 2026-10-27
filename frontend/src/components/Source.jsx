// Each card gets one of four playing-card colours and its concept's initial as the corner index.
export const tone = (i) => `tone-${i % 4}`;
export const letter = (card) => (card.keyword.match(/[a-z0-9]/i)?.[0] ?? "?").toUpperCase();

export function Sparkle({ style, color = "currentColor" }) {
  return (
    <svg className="sparkle" style={style} viewBox="0 0 24 24" aria-hidden="true">
      <path fill={color} d="M12 2c.6 4.6 2.4 6.9 7 8-4.6 1.1-6.4 3.4-7 8-.6-4.6-2.4-6.9-7-8 4.6-1.1 6.4-3.4 7-8z" />
      <circle cx="20" cy="19" r="1.6" fill={color} />
    </svg>
  );
}

// Source sentence with the answer highlighted, so the student sees where it came from.
export function Source({ card }) {
  const text = card.source;
  const answer = card.answer.replace(/\.$/, "");
  const i = text.toLowerCase().indexOf(answer.toLowerCase());
  return (
    <div className="source">
      <span className="pg">p.{card.page}</span>
      {i < 0 ? text : (
        <>
          {text.slice(0, i)}
          <mark>{text.slice(i, i + answer.length)}</mark>
          {text.slice(i + answer.length)}
        </>
      )}
    </div>
  );
}

// "Fill in the blank: X _____ Y" -> X [blank] Y
export function QuestionText({ card }) {
  if (card.kind !== "cloze") return card.question;
  const parts = card.question.replace(/^Fill in the blank:\s*/, "").split("_____");
  return parts.map((p, i) => (
    <span key={i}>
      {p}
      {i < parts.length - 1 && <span className="blank" aria-label="blank" />}
    </span>
  ));
}

export function KindBadge({ kind }) {
  return <span className={`badge ${kind === "definition" ? "def" : "cloze"}`}>
    {kind === "definition" ? "Definition" : "Fill in the blank"}
  </span>;
}
