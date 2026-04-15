import { useState, useEffect } from "react";

const base = {
  position: "fixed",
  top: "50%",
  right: "2rem",
  transform: "translateY(-50%) translateX(0)",
  width: "min(360px, 80vw)",
  maxHeight: "70vh",
  overflowY: "auto",
  padding: "1.5rem",
  borderRadius: "16px",
  background: "rgba(10, 8, 30, 0.92)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  border: "1px solid rgba(255, 255, 255, 0.1)",
  color: "#fff",
  zIndex: 120,
  transition: "opacity 0.4s ease, transform 0.4s ease",
};

const visible = { opacity: 1, transform: "translateY(-50%) translateX(0)" };
const hidden = { opacity: 0, transform: "translateY(-50%) translateX(20px)", pointerEvents: "none" };

const s = {
  title: {
    fontSize: "0.95rem",
    fontWeight: 700,
    marginBottom: "1rem",
    letterSpacing: "0.3px",
    color: "#fff",
  },
  subtitle: {
    fontSize: "0.65rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "1.5px",
    color: "rgba(255,255,255,0.35)",
    marginBottom: "0.5rem",
  },
  fact: {
    fontSize: "0.82rem",
    lineHeight: 1.6,
    color: "rgba(255,255,255,0.85)",
    padding: "0.4rem 0",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
  },
  bullet: {
    color: "#60a5fa",
    marginRight: "0.5rem",
    fontWeight: 700,
  },
  th: {
    fontSize: "0.7rem",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "1px",
    color: "rgba(255,255,255,0.5)",
    padding: "0.5rem 0.6rem",
    textAlign: "left",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
  },
  td: {
    fontSize: "0.8rem",
    color: "rgba(255,255,255,0.85)",
    padding: "0.45rem 0.6rem",
    borderBottom: "1px solid rgba(255,255,255,0.04)",
  },
  timelineDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#60a5fa",
    flexShrink: 0,
    marginTop: "0.3rem",
  },
  timelineLine: {
    width: "2px",
    background: "rgba(255,255,255,0.08)",
    flexShrink: 0,
    alignSelf: "stretch",
    marginLeft: "3px",
  },
  timelineYear: {
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "#60a5fa",
    minWidth: "3rem",
  },
  timelineLabel: {
    fontSize: "0.8rem",
    color: "rgba(255,255,255,0.85)",
    lineHeight: 1.5,
  },
  concept: {
    display: "inline-block",
    padding: "0.3rem 0.7rem",
    margin: "0.25rem",
    borderRadius: "999px",
    fontSize: "0.78rem",
    fontWeight: 500,
    border: "1px solid rgba(255,255,255,0.12)",
    color: "rgba(255,255,255,0.85)",
  },
  citation: {
    fontSize: "0.78rem",
    lineHeight: 1.6,
    color: "rgba(255,255,255,0.7)",
    padding: "0.35rem 0",
    fontStyle: "italic",
  },
  citationNum: {
    color: "#60a5fa",
    fontWeight: 700,
    fontStyle: "normal",
    marginRight: "0.4rem",
  },
  closeBtn: {
    position: "absolute",
    top: "0.75rem",
    right: "0.75rem",
    background: "none",
    border: "none",
    color: "rgba(255,255,255,0.35)",
    fontSize: "1.1rem",
    cursor: "pointer",
    padding: "0.2rem",
    lineHeight: 1,
  },
};

// Random pastel-ish backgrounds for concept cloud
const conceptColors = [
  "rgba(96,165,250,0.15)",
  "rgba(74,222,128,0.15)",
  "rgba(251,191,36,0.15)",
  "rgba(248,113,113,0.15)",
  "rgba(167,139,250,0.15)",
  "rgba(56,189,248,0.15)",
];

function KeyFacts({ data }) {
  return (
    <>
      <div style={s.subtitle}>Key Facts</div>
      <div style={s.title}>{data.title}</div>
      {data.facts.map((fact, i) => (
        <div key={i} style={s.fact}>
          <span style={s.bullet}>&#x2022;</span>
          {fact}
        </div>
      ))}
    </>
  );
}

function ComparisonTable({ data }) {
  return (
    <>
      <div style={s.subtitle}>Comparison</div>
      <div style={s.title}>{data.title}</div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {(data.columns || []).map((col, i) => (
                <th key={i} style={s.th}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(data.rows || []).map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} style={s.td}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Timeline({ data }) {
  return (
    <>
      <div style={s.subtitle}>Timeline</div>
      <div style={s.title}>{data.title}</div>
      {(data.events || []).map((ev, i) => (
        <div key={i} style={{ display: "flex", gap: "0.75rem", marginBottom: "0.75rem" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
            <div style={s.timelineDot} />
            {i < data.events.length - 1 && <div style={{ ...s.timelineLine, minHeight: "20px" }} />}
          </div>
          <div>
            <div style={s.timelineYear}>{ev.year}</div>
            <div style={s.timelineLabel}>{ev.label}</div>
          </div>
        </div>
      ))}
    </>
  );
}

function ConceptCloud({ data }) {
  return (
    <>
      <div style={s.subtitle}>Concepts</div>
      <div style={s.title}>{data.title}</div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.15rem" }}>
        {(data.concepts || []).map((concept, i) => (
          <span
            key={i}
            style={{
              ...s.concept,
              background: conceptColors[i % conceptColors.length],
            }}
          >
            {concept}
          </span>
        ))}
      </div>
    </>
  );
}

function Citations({ data }) {
  return (
    <>
      <div style={s.subtitle}>Sources</div>
      <div style={s.title}>{data.title}</div>
      {(data.citations || []).map((cit, i) => (
        <div key={i} style={s.citation}>
          <span style={s.citationNum}>[{i + 1}]</span>
          {cit}
        </div>
      ))}
    </>
  );
}

const renderers = {
  key_facts: KeyFacts,
  comparison_table: ComparisonTable,
  timeline: Timeline,
  citations: Citations,
};

export default function Popup({ data, onDismiss }) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!data) return;

    // Animate in
    const inTimer = setTimeout(() => setShow(true), 50);

    // Auto-dismiss after TTL
    const ttl = (data.ttl || 10) * 1000;
    const outTimer = setTimeout(() => {
      setShow(false);
      setTimeout(() => onDismiss(), 400);
    }, ttl);

    return () => {
      clearTimeout(inTimer);
      clearTimeout(outTimer);
    };
  }, [data, onDismiss]);

  if (!data) return null;

  const Renderer = renderers[data.type];
  if (!Renderer) return null;

  return (
    <div style={{ ...base, ...(show ? visible : hidden) }}>
      <button
        style={s.closeBtn}
        onClick={() => {
          setShow(false);
          setTimeout(() => onDismiss(), 400);
        }}
      >
        &times;
      </button>
      <Renderer data={data} />
    </div>
  );
}
