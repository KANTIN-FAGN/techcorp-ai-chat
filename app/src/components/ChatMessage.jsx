import { useState } from "react";
import { useSpeechSynthesis } from "../lib/useSpeechSynthesis.js";
import { useTypewriter } from "../lib/useTypewriter.js";
import BrandIcon from "./BrandIcon.jsx";

export default function ChatMessage({ id, role, content, isStreaming, onRegenerate, regenerateDisabled }) {
  const isUser = role === "user";
  const [copied, setCopied] = useState(false);
  const { isSpeaking, isSupported: ttsSupported, speak, stop } = useSpeechSynthesis();
  const displayedContent = useTypewriter(content, isStreaming);
  const isRevealing = isStreaming || displayedContent.length < content.length;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard unavailable — ignore
    }
  }

  const showActions = !isUser && !isRevealing && content;

  return (
    <div className={`message-row ${isUser ? "message-row--user" : "message-row--assistant"}`}>
      {!isUser && (
        <div className="avatar avatar--assistant" aria-hidden="true">
          <BrandIcon />
        </div>
      )}

      <div className="message-col">
        {!isUser && <span className="message-label">TechCorp AI</span>}
        <div className={`bubble ${isUser ? "bubble--user" : "bubble--assistant"}`}>
          {isStreaming && !content ? (
            <div className="typing-dots" aria-label="TechCorp AI est en train d'écrire">
              <span />
              <span />
              <span />
            </div>
          ) : (
            <p>
              {displayedContent}
              {isRevealing && <span className="cursor" aria-hidden="true" />}
            </p>
          )}
        </div>

        {showActions && (
          <div className="message-actions">
            <button type="button" className="message-action" onClick={handleCopy} aria-label="Copier la réponse">
              {copied ? (
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M5 12l4 4 10-10" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" strokeWidth="1.6" />
                  <path d="M5 15V6a1 1 0 011-1h9" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                </svg>
              )}
              {copied ? "Copié" : "Copier"}
            </button>

            {onRegenerate && (
              <button
                type="button"
                className="message-action"
                onClick={() => onRegenerate(id)}
                disabled={regenerateDisabled}
                aria-label="Régénérer la réponse"
              >
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    d="M4 12a8 8 0 0114-5.3M20 12a8 8 0 01-14 5.3M4 4v5h5M20 20v-5h-5"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                Régénérer
              </button>
            )}

            {ttsSupported && (
              <button
                type="button"
                className="message-action"
                onClick={() => (isSpeaking ? stop() : speak(content))}
                aria-label={isSpeaking ? "Arrêter la lecture" : "Écouter la réponse"}
              >
                {isSpeaking ? (
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="6" y="6" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.6" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path
                      d="M4 9v6h4l5 4V5L8 9H4z"
                      stroke="currentColor"
                      strokeWidth="1.6"
                      strokeLinejoin="round"
                    />
                    <path d="M16.5 9a4 4 0 010 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                  </svg>
                )}
                {isSpeaking ? "Arrêter" : "Écouter"}
              </button>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <div className="avatar avatar--user" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.6" />
            <path d="M5 20c0-3.6 3.13-6 7-6s7 2.4 7 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
        </div>
      )}
    </div>
  );
}
