import { Component } from "react";

const styles = {
  container: {
    position: "fixed",
    inset: 0,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
    zIndex: 9999,
  },
  card: {
    textAlign: "center",
    maxWidth: "460px",
    padding: "2.5rem",
  },
  title: {
    fontSize: "1.4rem",
    fontWeight: 700,
    color: "#fff",
    marginBottom: "0.75rem",
  },
  message: {
    fontSize: "0.9rem",
    color: "rgba(255, 255, 255, 0.6)",
    lineHeight: 1.6,
    marginBottom: "1.5rem",
  },
  button: {
    padding: "0.6rem 1.8rem",
    borderRadius: "999px",
    border: "1px solid rgba(255, 255, 255, 0.3)",
    background: "rgba(255, 255, 255, 0.1)",
    color: "#fff",
    fontSize: "0.9rem",
    fontWeight: 500,
    cursor: "pointer",
    transition: "all 0.2s",
  },
};

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={styles.container}>
          <div style={styles.card}>
            <div style={styles.title}>Something went wrong</div>
            <div style={styles.message}>
              The presentation hit an unexpected error. Click below to reload and reconnect.
            </div>
            <button
              style={styles.button}
              onClick={() => this.setState({ hasError: false })}
              onMouseOver={(e) => (e.target.style.background = "rgba(255, 255, 255, 0.2)")}
              onMouseOut={(e) => (e.target.style.background = "rgba(255, 255, 255, 0.1)")}
            >
              Reconnect
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
