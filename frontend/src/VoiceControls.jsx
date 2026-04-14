const stateLabels = {
  listening: "Listening...",
  thinking: "Thinking...",
  speaking: "AI Speaking...",
};

const styles = {
  container: {
    position: "fixed",
    bottom: "1.5rem",
    left: "50%",
    transform: "translateX(-50%)",
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    padding: "0.5rem 1rem",
    borderRadius: "999px",
    background: "rgba(0, 0, 0, 0.5)",
    backdropFilter: "blur(10px)",
    WebkitBackdropFilter: "blur(10px)",
    border: "1px solid rgba(255, 255, 255, 0.1)",
    zIndex: 100,
  },
  label: {
    fontSize: "0.8rem",
    color: "rgba(255, 255, 255, 0.7)",
    fontWeight: 500,
    letterSpacing: "0.5px",
  },
  dot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    flexShrink: 0,
  },
};

const cssAnimations = `
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.8); }
  }
  @keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
  }
  @keyframes wave1 {
    0%, 100% { height: 4px; }
    50% { height: 14px; }
  }
  @keyframes wave2 {
    0%, 100% { height: 6px; }
    50% { height: 12px; }
  }
  @keyframes wave3 {
    0%, 100% { height: 4px; }
    50% { height: 16px; }
  }
`;

function Indicator({ state }) {
  if (state === "listening") {
    return (
      <span
        style={{
          ...styles.dot,
          background: "#4ade80",
          animation: "pulse 1.5s ease-in-out infinite",
        }}
      />
    );
  }

  if (state === "thinking") {
    return (
      <span
        style={{
          width: "14px",
          height: "14px",
          border: "2px solid rgba(255, 255, 255, 0.2)",
          borderTopColor: "#fbbf24",
          borderRadius: "50%",
          animation: "spin 0.8s linear infinite",
          flexShrink: 0,
        }}
      />
    );
  }

  if (state === "speaking") {
    return (
      <span
        style={{
          display: "flex",
          alignItems: "center",
          gap: "2px",
          height: "16px",
        }}
      >
        {[1, 2, 3].map((n) => (
          <span
            key={n}
            style={{
              width: "3px",
              background: "#60a5fa",
              borderRadius: "2px",
              animation: `wave${n} 0.8s ease-in-out infinite`,
              animationDelay: `${(n - 1) * 0.15}s`,
            }}
          />
        ))}
      </span>
    );
  }

  return (
    <span
      style={{
        ...styles.dot,
        background: "rgba(255, 255, 255, 0.3)",
        animation: "pulse 2s ease-in-out infinite",
      }}
    />
  );
}

export default function VoiceControls({ state }) {
  const label = stateLabels[state] || "Connecting...";

  return (
    <>
      <style>{cssAnimations}</style>
      <div style={styles.container}>
        <Indicator state={state} />
        <span style={styles.label}>{label}</span>
      </div>
    </>
  );
}
