import { useState, useEffect, useCallback } from "react";
import {
  useDataChannel,
  useVoiceAssistant,
} from "@livekit/components-react";
import { SLIDES } from "./slides";
import SlideViewer from "./SlideViewer";
import VoiceControls from "./VoiceControls";
import Captions from "./Captions";
import QAPanel from "./QAPanel";
import Popup from "./Popup";

export default function PresentationRoom() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [showCaptions, setShowCaptions] = useState(false);
  const [popupData, setPopupData] = useState(null);
  const { state: agentState, agentTranscriptions } = useVoiceAssistant();

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

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        setCurrentSlide((prev) => Math.min(prev + 1, SLIDES.length - 1));
      } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        setCurrentSlide((prev) => Math.max(prev - 1, 0));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

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
    </>
  );
}
