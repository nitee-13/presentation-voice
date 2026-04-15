import { useEffect, useState } from "react";

const styles = {
  container: {
    position: "relative",
    width: "100vw",
    height: "100vh",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
    background: "#1a1a2e",
  },
  image: {
    width: "100vw",
    height: "100vh",
    objectFit: "contain",
    transition: "opacity 0.5s ease-in-out",
  },
  imageVisible: {
    opacity: 1,
  },
  imageHidden: {
    opacity: 0,
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
    <div style={styles.container}>
      <img
        src={displaySlide.image}
        alt={displaySlide.title || `Slide ${index + 1}`}
        style={{
          ...styles.image,
          ...(visible ? styles.imageVisible : styles.imageHidden),
        }}
      />
      <div style={styles.counter}>
        {index + 1} / {total}
      </div>
    </div>
  );
}
