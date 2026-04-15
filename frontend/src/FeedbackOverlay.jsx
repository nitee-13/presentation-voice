import { useState, useCallback } from "react";
import { useDataChannel } from "@livekit/components-react";

const s = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(0, 0, 0, 0.7)",
    backdropFilter: "blur(8px)",
    WebkitBackdropFilter: "blur(8px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 300,
    transition: "opacity 0.3s ease",
  },
  card: {
    width: "min(440px, 90vw)",
    padding: "2rem",
    borderRadius: "20px",
    background: "rgba(15, 12, 41, 0.95)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    textAlign: "center",
    color: "#fff",
  },
  title: {
    fontSize: "1.2rem",
    fontWeight: 700,
    marginBottom: "0.5rem",
  },
  subtitle: {
    fontSize: "0.85rem",
    color: "rgba(255, 255, 255, 0.5)",
    marginBottom: "1.5rem",
  },
  stars: {
    display: "flex",
    justifyContent: "center",
    gap: "0.75rem",
    marginBottom: "1.25rem",
  },
  star: {
    fontSize: "2.5rem",
    cursor: "pointer",
    transition: "transform 0.2s, color 0.2s",
    userSelect: "none",
  },
  comment: {
    margin: "1rem auto",
    padding: "0.75rem 1rem",
    borderRadius: "12px",
    background: "rgba(255, 255, 255, 0.05)",
    border: "1px solid rgba(255, 255, 255, 0.08)",
    fontSize: "0.85rem",
    color: "rgba(255, 255, 255, 0.8)",
    lineHeight: 1.6,
    textAlign: "left",
    maxWidth: "360px",
    fontStyle: "italic",
  },
  commentLabel: {
    fontSize: "0.65rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "1px",
    color: "rgba(255, 255, 255, 0.35)",
    marginBottom: "0.3rem",
    textAlign: "left",
  },
  phase: {
    fontSize: "0.9rem",
    color: "rgba(255, 255, 255, 0.7)",
    lineHeight: 1.6,
    minHeight: "1.5rem",
    marginTop: "0.75rem",
  },
  skip: {
    marginTop: "1.5rem",
    fontSize: "0.7rem",
    color: "rgba(255, 255, 255, 0.3)",
    letterSpacing: "0.5px",
  },
  doneCheck: {
    fontSize: "2.5rem",
    marginBottom: "0.5rem",
  },
};

function parsePayload(msg) {
  let text;
  if (typeof msg.payload === "string") {
    text = msg.payload;
  } else if (msg.payload instanceof Uint8Array) {
    text = new TextDecoder().decode(msg.payload);
  } else if (msg.payload instanceof ArrayBuffer) {
    text = new TextDecoder().decode(new Uint8Array(msg.payload));
  } else {
    text = typeof msg === "string" ? msg : new TextDecoder().decode(msg);
  }
  return JSON.parse(text);
}

export default function FeedbackOverlay({ onDone }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [comment, setComment] = useState("");
  const [phase, setPhase] = useState("rating");

  const onFeedbackUpdate = useCallback((msg) => {
    try {
      const data = parsePayload(msg);
      if (typeof data.rating === "number" && data.rating >= 1 && data.rating <= 5) {
        setRating(data.rating);
      }
      if (data.comment) {
        setComment(data.comment);
      }
      if (data.phase) {
        setPhase(data.phase);
      }
      if (data.phase === "done") {
        setTimeout(() => onDone(), 3000);
      }
    } catch (err) {
      console.error("Failed to parse feedback_update:", err);
    }
  }, [onDone]);

  useDataChannel("feedback_update", onFeedbackUpdate);

  const phaseText = {
    rating: "Speak your rating or tap a star...",
    comment: "Share any thoughts — or say 'no' to skip...",
    confirm: "Confirm to submit, or say 'no' to redo...",
    done: "Feedback submitted!",
  };

  return (
    <div style={s.backdrop}>
      <div style={s.card}>
        {phase === "done" ? (
          <>
            <div style={s.doneCheck}>&#10003;</div>
            <div style={s.title}>Thank you!</div>
            <div style={s.subtitle}>Your feedback has been submitted</div>
          </>
        ) : (
          <>
            <div style={s.title}>How was the presentation?</div>
            <div style={s.subtitle}>Rate your experience with Devi</div>

            <div style={s.stars}>
              {[1, 2, 3, 4, 5].map((n) => (
                <span
                  key={n}
                  style={{
                    ...s.star,
                    color: n <= (hover || rating) ? "#fbbf24" : "rgba(255,255,255,0.15)",
                    transform: n <= (hover || rating) ? "scale(1.1)" : "scale(1)",
                  }}
                  onMouseEnter={() => setHover(n)}
                  onMouseLeave={() => setHover(0)}
                  onClick={() => setRating(n)}
                >
                  &#9733;
                </span>
              ))}
            </div>

            {comment && (phase === "confirm" || phase === "comment") && (
              <div style={{ maxWidth: "360px", margin: "0 auto" }}>
                <div style={s.commentLabel}>Your feedback</div>
                <div style={s.comment}>&ldquo;{comment}&rdquo;</div>
              </div>
            )}

            <div style={s.phase}>{phaseText[phase] || ""}</div>
            <div style={s.skip}>Press Skip & Exit to leave without feedback</div>
          </>
        )}
      </div>
    </div>
  );
}
