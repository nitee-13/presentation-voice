import { useState, useEffect, useCallback, useRef } from "react";
import {
  useDataChannel,
  useVoiceAssistant,
  useRoomContext,
  useLocalParticipant,
} from "@livekit/components-react";
import { SLIDES } from "./slides";
import SlideViewer from "./SlideViewer";
import VoiceControls from "./VoiceControls";
import Captions from "./Captions";
import QAPanel from "./QAPanel";
import Popup from "./Popup";
import FeedbackOverlay from "./FeedbackOverlay";

export default function PresentationRoom() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [showCaptions, setShowCaptions] = useState(false);
  const [popupData, setPopupData] = useState(null);
  const [feedbackActive, setFeedbackActive] = useState(false);
  const { state: agentState, agentTranscriptions } = useVoiceAssistant();
  const room = useRoomContext();
  const { localParticipant } = useLocalParticipant();
  const slideRef = useRef(0);

  const onDataReceived = useCallback((msg) => {
    try {
      // msg.payload can be Uint8Array, ArrayBuffer, or string
      let text;
      if (typeof msg.payload === "string") {
        text = msg.payload;
      } else if (msg.payload instanceof Uint8Array) {
        text = new TextDecoder().decode(msg.payload);
      } else if (msg.payload instanceof ArrayBuffer) {
        text = new TextDecoder().decode(new Uint8Array(msg.payload));
      } else {
        // Fallback: try to decode the msg itself
        text = typeof msg === "string" ? msg : new TextDecoder().decode(msg);
      }

      const data = JSON.parse(text);
      console.log("Slide change received:", data);
      if (
        typeof data.slideIndex === "number" &&
        data.slideIndex >= 0 &&
        data.slideIndex < SLIDES.length
      ) {
        setCurrentSlide(data.slideIndex);
      }
    } catch (err) {
      console.error("Failed to parse slide_change message:", err, msg);
    }
  }, []);

  useDataChannel("slide_change", onDataReceived);

  const onPopupReceived = useCallback((msg) => {
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
      console.log("Popup received:", data);
      setPopupData(data);
    } catch (err) {
      console.error("Failed to parse ui_popup message:", err);
    }
  }, []);

  useDataChannel("ui_popup", onPopupReceived);

  // Keep ref in sync with all slide changes (backend + keyboard)
  useEffect(() => {
    slideRef.current = currentSlide;
  }, [currentSlide]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      const prev = slideRef.current;
      let next;
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        next = Math.min(prev + 1, SLIDES.length - 1);
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        next = Math.max(prev - 1, 0);
      } else {
        return;
      }
      if (next !== prev) {
        slideRef.current = next;
        setCurrentSlide(next);
        localParticipant?.publishData(
          JSON.stringify({ slideIndex: next }),
          { topic: "user_slide_nav" }
        );
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [localParticipant]);

  return (
    <>
      <SlideViewer
        slide={SLIDES[currentSlide]}
        index={currentSlide}
        total={SLIDES.length}
      />
      <Popup data={popupData} onDismiss={() => setPopupData(null)} />
      <QAPanel />
      <Captions
        agentTranscriptions={agentTranscriptions}
        show={showCaptions}
        onToggle={() => setShowCaptions((prev) => !prev)}
      />
      <VoiceControls state={agentState} />
      {feedbackActive && (
        <FeedbackOverlay onDone={() => room.disconnect()} />
      )}
      <button
        onClick={() => {
          if (feedbackActive) {
            room.disconnect();
          } else {
            setFeedbackActive(true);
            localParticipant?.publishData(
              JSON.stringify({ action: "start_feedback" }),
              { topic: "feedback_control" }
            );
          }
        }}
        style={{
          position: "fixed",
          top: "1.5rem",
          left: "2rem",
          padding: "0.5rem 1rem",
          borderRadius: "999px",
          border: "1px solid rgba(255, 80, 80, 0.4)",
          background: "rgba(255, 50, 50, 0.15)",
          backdropFilter: "blur(10px)",
          WebkitBackdropFilter: "blur(10px)",
          color: "rgba(255, 255, 255, 0.8)",
          fontSize: "0.8rem",
          fontWeight: 500,
          cursor: "pointer",
          zIndex: 400,
          transition: "all 0.2s",
          letterSpacing: "0.5px",
        }}
        onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255, 50, 50, 0.35)")}
        onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255, 50, 50, 0.15)")}
      >
        {feedbackActive ? "Skip & Exit" : "End Session"}
      </button>
    </>
  );
}
