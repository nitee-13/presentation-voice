import { useState, useEffect, useRef } from "react";

const styles = {
  overlay: {
    position: "fixed",
    bottom: "4.5rem",
    left: "50%",
    transform: "translateX(-50%)",
    width: "min(90vw, 800px)",
    padding: "0.5rem 1.25rem",
    borderRadius: "12px",
    background: "transparent",
    zIndex: 90,
    transition: "opacity 0.3s ease, transform 0.3s ease",
    overflow: "hidden",
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
  },
  visible: {
    opacity: 1,
    transform: "translateX(-50%) translateY(0)",
  },
  hidden: {
    opacity: 0,
    transform: "translateX(-50%) translateY(10px)",
    pointerEvents: "none",
  },
  line: {
    fontSize: "0.95rem",
    lineHeight: 1.5,
    color: "rgba(0, 0, 0, 0.85)",
    margin: 0,
    display: "-webkit-box",
    WebkitLineClamp: 2,
    WebkitBoxOrient: "vertical",
    overflow: "hidden",
  },
  label: {
    fontSize: "0.7rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "1px",
    marginRight: "0.5rem",
  },
  toggleBtn: {
    position: "fixed",
    bottom: "1.5rem",
    left: "2rem",
    display: "flex",
    alignItems: "center",
    gap: "0.35rem",
    padding: "0.4rem 0.75rem",
    borderRadius: "999px",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    background: "rgba(0, 0, 0, 0.5)",
    backdropFilter: "blur(10px)",
    WebkitBackdropFilter: "blur(10px)",
    color: "rgba(255, 255, 255, 0.7)",
    fontSize: "0.75rem",
    fontWeight: 500,
    cursor: "pointer",
    zIndex: 100,
    transition: "all 0.2s",
    letterSpacing: "0.5px",
  },
};

export default function Captions({ agentTranscriptions, show, onToggle }) {
  const [captionText, setCaptionText] = useState("");
  const scrollRef = useRef(null);

  // Build caption text from the latest agent transcription segments
  useEffect(() => {
    if (!agentTranscriptions || agentTranscriptions.length === 0) {
      return;
    }

    // Get the most recent segments and combine their text
    const recent = agentTranscriptions.slice(-15);
    const text = recent
      .map((seg) => seg.text)
      .join("")
      .trim();

    if (text) {
      setCaptionText(text);
    }
  }, [agentTranscriptions]);

  // Auto-scroll to bottom when caption text updates
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [captionText]);

  return (
    <>
      {/* CC toggle button */}
      <button
        onClick={onToggle}
        style={{
          ...styles.toggleBtn,
          background: show
            ? "rgba(255, 255, 255, 0.15)"
            : "rgba(0, 0, 0, 0.5)",
          borderColor: show
            ? "rgba(255, 255, 255, 0.3)"
            : "rgba(255, 255, 255, 0.15)",
        }}
        onMouseOver={(e) =>
          (e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)")
        }
        onMouseOut={(e) =>
          (e.currentTarget.style.background = show
            ? "rgba(255, 255, 255, 0.15)"
            : "rgba(0, 0, 0, 0.5)")
        }
        title={show ? "Hide captions" : "Show captions"}
      >
        <span style={{ fontSize: "1rem" }}>CC</span>
        <span>{show ? "ON" : "OFF"}</span>
      </button>

      {/* Caption overlay */}
      {captionText && (
        <div
          ref={scrollRef}
          style={{
            ...styles.overlay,
            ...(show ? styles.visible : styles.hidden),
          }}
        >
          <p style={styles.line}>
            <span style={{ ...styles.label, color: "#2563eb" }}>Devi</span>
            {captionText}
          </p>
        </div>
      )}
    </>
  );
}
