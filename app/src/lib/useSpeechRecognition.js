import { useEffect, useRef, useState } from "react";

/** Wraps the browser's SpeechRecognition API (Chrome/Edge/Safari) for dictation. */
export function useSpeechRecognition({ lang = "fr-FR" } = {}) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognitionRef.current = recognition;

    return () => recognition.stop();
  }, [lang]);

  function start(onResult) {
    const recognition = recognitionRef.current;
    if (!recognition || isListening) return;

    recognition.onresult = (event) => {
      let transcript = "";
      for (let i = 0; i < event.results.length; i++) {
        transcript += event.results[i][0].transcript;
      }
      onResult(transcript);
    };
    recognition.onend = () => setIsListening(false);
    recognition.onerror = () => setIsListening(false);

    try {
      recognition.start();
      setIsListening(true);
    } catch {
      // already started — ignore
    }
  }

  function stop() {
    recognitionRef.current?.stop();
    setIsListening(false);
  }

  return { isListening, isSupported, start, stop };
}
