import { useState, useEffect, useRef, useCallback } from "react";
import { useDataChannel } from "@livekit/components-react";

const styles = {
  toggleBtn: {
    position: "fixed",
    top: "1.5rem",
    right: "2rem",
    display: "flex",
    alignItems: "center",
    gap: "0.4rem",
    padding: "0.5rem 1rem",
    borderRadius: "999px",
    border: "1px solid rgba(255, 255, 255, 0.15)",
    background: "rgba(0, 0, 0, 0.5)",
    backdropFilter: "blur(10px)",
    WebkitBackdropFilter: "blur(10px)",
    color: "rgba(255, 255, 255, 0.7)",
    fontSize: "0.8rem",
    fontWeight: 500,
    cursor: "pointer",
    zIndex: 200,
    transition: "all 0.2s",
    letterSpacing: "0.5px",
  },
  badge: {
    minWidth: "18px",
    height: "18px",
    borderRadius: "999px",
    background: "#60a5fa",
    color: "#fff",
    fontSize: "0.65rem",
    fontWeight: 700,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "0 5px",
  },
  panel: {
    position: "fixed",
    top: 0,
    right: 0,
    width: "min(400px, 85vw)",
    height: "100vh",
    background: "rgba(10, 8, 30, 0.95)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    borderLeft: "1px solid rgba(255, 255, 255, 0.1)",
    zIndex: 150,
    display: "flex",
    flexDirection: "column",
    transition: "transform 0.3s ease",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "1.25rem 1.5rem",
    borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
  },
  headerTitle: {
    fontSize: "1rem",
    fontWeight: 600,
    color: "#fff",
    letterSpacing: "0.5px",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "rgba(255, 255, 255, 0.5)",
    fontSize: "1.4rem",
    cursor: "pointer",
    padding: "0.25rem",
    lineHeight: 1,
  },
  list: {
    flex: 1,
    overflowY: "auto",
    padding: "1rem 1.5rem",
  },
  entry: {
    marginBottom: "1.25rem",
    paddingBottom: "1.25rem",
    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
  },
  timestamp: {
    fontSize: "0.65rem",
    color: "rgba(255, 255, 255, 0.3)",
    marginBottom: "0.5rem",
    letterSpacing: "0.5px",
  },
  userMsg: {
    fontSize: "0.85rem",
    color: "rgba(255, 255, 255, 0.6)",
    marginBottom: "0.4rem",
    lineHeight: 1.5,
  },
  aiMsg: {
    fontSize: "0.85rem",
    color: "rgba(255, 255, 255, 0.9)",
    lineHeight: 1.5,
  },
  label: {
    fontSize: "0.65rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "1px",
    marginRight: "0.4rem",
  },
  empty: {
    textAlign: "center",
    color: "rgba(255, 255, 255, 0.3)",
    fontSize: "0.85rem",
    marginTop: "3rem",
  },
};

function formatTime(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export default function QAPanel() {
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState([]);
  const listRef = useRef(null);

  const onQAReceived = useCallback((msg) => {
    try {
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

      const data = JSON.parse(text);
      if (data.user && data.assistant) {
        setEntries((prev) => [...prev, { ...data, timestamp: Date.now() }]);
      }
    } catch (err) {
      console.error("Failed to parse qa_entry:", err);
    }
  }, []);

  useDataChannel("qa_entry", onQAReceived);

  // Auto-scroll to bottom when new entry arrives
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [entries]);

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen((prev) => !prev)}
        style={{
          ...styles.toggleBtn,
          background: open
            ? "rgba(255, 255, 255, 0.15)"
            : "rgba(0, 0, 0, 0.5)",
        }}
        onMouseOver={(e) =>
          (e.currentTarget.style.background = "rgba(255, 255, 255, 0.2)")
        }
        onMouseOut={(e) =>
          (e.currentTarget.style.background = open
            ? "rgba(255, 255, 255, 0.15)"
            : "rgba(0, 0, 0, 0.5)")
        }
      >
        <span>Q&A</span>
        {entries.length > 0 && (
          <span style={styles.badge}>{entries.length}</span>
        )}
      </button>

      {/* Slide-out panel */}
      <div
        style={{
          ...styles.panel,
          transform: open ? "translateX(0)" : "translateX(100%)",
        }}
      >
        <div style={styles.header}>
          <span style={styles.headerTitle}>Q&A History</span>
          <button style={styles.closeBtn} onClick={() => setOpen(false)}>
            &times;
          </button>
        </div>

        <div style={styles.list} ref={listRef}>
          {entries.length === 0 ? (
            <p style={styles.empty}>
              No questions yet. Ask something during the presentation!
            </p>
          ) : (
            entries.map((entry, i) => (
              <div key={i} style={styles.entry}>
                <div style={styles.timestamp}>{formatTime(entry.timestamp)}</div>
                <p style={styles.userMsg}>
                  <span style={{ ...styles.label, color: "#4ade80" }}>You</span>
                  {entry.user}
                </p>
                <p style={styles.aiMsg}>
                  <span style={{ ...styles.label, color: "#60a5fa" }}>AI</span>
                  {entry.assistant}
                </p>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
