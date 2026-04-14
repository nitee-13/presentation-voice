import { useState, useEffect, useCallback } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
} from "@livekit/components-react";
import "@livekit/components-styles";
import PresentationRoom from "./PresentationRoom";

const LIVEKIT_URL = import.meta.env.VITE_LIVEKIT_URL;
const TOKEN_SERVER_URL = import.meta.env.VITE_TOKEN_SERVER_URL;

function generateIdentity() {
  return `user-${Math.random().toString(36).substring(2, 9)}`;
}

export default function App() {
  const [token, setToken] = useState(null);
  const [error, setError] = useState(null);
  const [started, setStarted] = useState(false);

  const fetchToken = useCallback(async () => {
    try {
      const identity = generateIdentity();
      const response = await fetch(`${TOKEN_SERVER_URL}/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity }),
      });

      if (!response.ok) {
        throw new Error(`Token server returned ${response.status}`);
      }

      const data = await response.json();
      setToken(data.token || data.accessToken);
    } catch (err) {
      console.error("Failed to fetch token:", err);
      setError(err.message);
    }
  }, []);

  // Show "Start Presentation" button first (required for browser audio policy)
  if (!started) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <h1 style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>AI Voice Presentation</h1>
          <p style={{ marginBottom: "2rem", opacity: 0.7 }}>The Future of AI</p>
          <button
            onClick={() => {
              setStarted(true);
              fetchToken();
            }}
            style={{
              padding: "0.8rem 2.5rem",
              border: "1px solid rgba(255,255,255,0.3)",
              borderRadius: "12px",
              background: "rgba(255,255,255,0.1)",
              color: "#fff",
              cursor: "pointer",
              fontSize: "1.1rem",
              transition: "all 0.2s",
            }}
            onMouseOver={(e) => (e.target.style.background = "rgba(255,255,255,0.2)")}
            onMouseOut={(e) => (e.target.style.background = "rgba(255,255,255,0.1)")}
          >
            Start Presentation
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <h2>Connection Error</h2>
          <p>{error}</p>
          <button
            onClick={() => {
              setError(null);
              fetchToken();
            }}
            style={{
              marginTop: "1rem",
              padding: "0.5rem 1.5rem",
              border: "1px solid rgba(255,255,255,0.3)",
              borderRadius: "8px",
              background: "transparent",
              color: "#fff",
              cursor: "pointer",
              fontSize: "0.9rem",
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!token) {
    return (
      <div className="loading-screen">
        <div className="loading-content">
          <div className="loading-spinner" />
          <p>Connecting to presentation...</p>
        </div>
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={LIVEKIT_URL}
      token={token}
      connect={true}
      audio={true}
      video={false}
      style={{ height: "100vh", width: "100vw" }}
    >
      <RoomAudioRenderer />
      <PresentationRoom />
    </LiveKitRoom>
  );
}
