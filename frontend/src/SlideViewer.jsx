import { useEffect, useState } from "react";

const styles = {
  container: {
    position: "relative",
    width: "100vw",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
    transition: "background 0.6s ease-in-out",
  },
  content: {
    maxWidth: "900px",
    width: "90%",
    padding: "2rem",
    transition: "opacity 0.5s ease-in-out, transform 0.5s ease-in-out",
  },
  contentVisible: {
    opacity: 1,
    transform: "translateY(0)",
  },
  contentHidden: {
    opacity: 0,
    transform: "translateY(30px)",
  },
  subtitle: {
    fontSize: "1rem",
    fontWeight: 500,
    textTransform: "uppercase",
    letterSpacing: "3px",
    color: "rgba(255, 255, 255, 0.6)",
    marginBottom: "0.75rem",
  },
  title: {
    fontSize: "clamp(2rem, 5vw, 3.5rem)",
    fontWeight: 700,
    color: "#ffffff",
    marginBottom: "2rem",
    lineHeight: 1.2,
  },
  divider: {
    width: "60px",
    height: "3px",
    background: "rgba(255, 255, 255, 0.4)",
    borderRadius: "2px",
    marginBottom: "2rem",
  },
  list: {
    listStyle: "none",
    padding: 0,
    margin: 0,
  },
  listItem: {
    fontSize: "clamp(1rem, 2vw, 1.25rem)",
    color: "rgba(255, 255, 255, 0.85)",
    lineHeight: 1.8,
    paddingLeft: "1.5rem",
    position: "relative",
    marginBottom: "0.5rem",
  },
  bullet: {
    position: "absolute",
    left: 0,
    color: "rgba(255, 255, 255, 0.4)",
  },
  counter: {
    position: "fixed",
    bottom: "1.5rem",
    right: "2rem",
    fontSize: "0.875rem",
    color: "rgba(255, 255, 255, 0.4)",
    fontWeight: 500,
    letterSpacing: "1px",
  },
};

export default function SlideViewer({ slide, index, total }) {
  const [visible, setVisible] = useState(true);
  const [displaySlide, setDisplaySlide] = useState(slide);

  useEffect(() => {
    setVisible(false);
    const timer = setTimeout(() => {
      setDisplaySlide(slide);
      setVisible(true);
    }, 300);
    return () => clearTimeout(timer);
  }, [slide]);

  return (
    <div style={{ ...styles.container, background: displaySlide.gradient }}>
      <div
        style={{
          ...styles.content,
          ...(visible ? styles.contentVisible : styles.contentHidden),
        }}
      >
        <div style={styles.subtitle}>{displaySlide.subtitle}</div>
        <h1 style={styles.title}>{displaySlide.title}</h1>
        <div style={styles.divider} />
        <ul style={styles.list}>
          {displaySlide.content.map((item, i) => (
            <li key={i} style={styles.listItem}>
              <span style={styles.bullet}>&#x2022;</span>
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div style={styles.counter}>
        {index + 1} / {total}
      </div>
    </div>
  );
}
