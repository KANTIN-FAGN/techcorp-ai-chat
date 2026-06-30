import { useState } from "react";

/** Wraps the browser's SpeechSynthesis API to read text aloud, one utterance at a time. */
export function useSpeechSynthesis({ lang = "fr-FR" } = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const isSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  function speak(text) {
    if (!isSupported || !text) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang;
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  function stop() {
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }

  return { isSpeaking, isSupported, speak, stop };
}
