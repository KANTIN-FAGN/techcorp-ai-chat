import { useRef } from "react";
import { useSpeechRecognition } from "../lib/useSpeechRecognition.js";

export default function ChatInput({ value, onChange, onSend, disabled, autoFocus }) {
  const textareaRef = useRef(null);
  const baseValueRef = useRef("");
  const { isListening, isSupported, start, stop } = useSpeechRecognition();

  function resize() {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  function handleChange(e) {
    onChange(e.target.value);
    resize();
  }

  function handleMicClick() {
    if (isListening) {
      stop();
      return;
    }
    baseValueRef.current = value ? `${value} ` : "";
    start((transcript) => {
      onChange((baseValueRef.current + transcript).trim());
      resize();
    });
  }

  return (
    <div className="chat-input">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleChange}
        onKeyDown={handleKeyDown}
        placeholder={isListening ? "Je vous écoute…" : "Demander à TechCorp AI…"}
        rows={1}
        disabled={disabled}
        autoFocus={autoFocus}
      />

      {value.trim() && !isListening ? (
        <button
          type="button"
          className="send-button"
          onClick={onSend}
          disabled={disabled}
          aria-label="Envoyer"
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      ) : (
        <button
          type="button"
          className={`chat-input__icon chat-input__icon--mic ${isListening ? "chat-input__icon--listening" : ""}`}
          onClick={handleMicClick}
          disabled={disabled || !isSupported}
          aria-label={isListening ? "Arrêter la dictée" : "Parler"}
          title={!isSupported ? "Dictée vocale non supportée par ce navigateur" : undefined}
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="9" y="3" width="6" height="11" rx="3" stroke="currentColor" strokeWidth="1.6" />
            <path d="M5 11a7 7 0 0014 0M12 18v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </button>
      )}
    </div>
  );
}
