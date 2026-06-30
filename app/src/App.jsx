import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import ChatMessage from "./components/ChatMessage.jsx";
import ChatInput from "./components/ChatInput.jsx";
import { streamChat, checkOllamaStatus, OLLAMA_MODEL } from "./lib/ollama.js";
import { useLocalStorage } from "./lib/useLocalStorage.js";

const DEFAULT_TITLE = "Nouvelle conversation";
const CONVERSATIONS_KEY = "techcorp-ai-chat:conversations";
const ACTIVE_ID_KEY = "techcorp-ai-chat:active-id";
const THEME_KEY = "techcorp-ai-chat:theme";

const SUGGESTIONS = [
  "Explique-moi le ratio dette/EBITDA",
  "Résume les tendances du marché obligataire",
  "Quels sont les risques d'un portefeuille trop concentré ?",
  "Compare le rendement obligataire et actions",
];

const GREETINGS = [
  "Comment ça va ?",
  "Prêt à analyser ?",
  "Par où commence-t-on ?",
  "Une question financière ?",
  "Que puis-je faire pour vous ?",
  "À quoi pensez-vous ?",
];

function randomGreeting() {
  return GREETINGS[Math.floor(Math.random() * GREETINGS.length)];
}

function createConversation() {
  return {
    id: crypto.randomUUID(),
    title: DEFAULT_TITLE,
    messages: [],
  };
}

function createMessage(role, content) {
  return { id: crypto.randomUUID(), role, content };
}

export default function App() {
  const [conversations, setConversations] = useLocalStorage(CONVERSATIONS_KEY, () => [createConversation()]);
  const [activeId, setActiveId] = useLocalStorage(ACTIVE_ID_KEY, () => conversations[0]?.id ?? null);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessageId, setStreamingMessageId] = useState(null);
  const [status, setStatus] = useState("checking");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useLocalStorage(THEME_KEY, "dark");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const abortRef = useRef(null);
  const scrollRef = useRef(null);
  const stickToBottomRef = useRef(true);

  const active = useMemo(
    () => conversations.find((c) => c.id === activeId) ?? conversations[0],
    [conversations, activeId]
  );
  const messages = active.messages;
  const isEmpty = messages.length === 0;
  const greeting = useMemo(() => randomGreeting(), [active.id]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    checkOllamaStatus().then((ok) => setStatus(ok ? "online" : "offline"));
    const interval = setInterval(() => {
      checkOllamaStatus().then((ok) => setStatus(ok ? "online" : "offline"));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (stickToBottomRef.current) {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    scrollToBottom(false);
  }, [active.id]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;

    function handleScroll() {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      const atBottom = distance < 80;
      stickToBottomRef.current = atBottom;
      setShowScrollButton(!atBottom);
    }

    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [isEmpty]);

  useEffect(() => {
    function handleKeyDown(e) {
      const isMod = e.metaKey || e.ctrlKey;
      if (isMod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        handleNewConversation();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  function scrollToBottom(smooth = true) {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    stickToBottomRef.current = true;
    setShowScrollButton(false);
  }

  function updateActiveMessages(updater) {
    setConversations((prev) =>
      prev.map((c) => (c.id === active.id ? { ...c, messages: updater(c.messages) } : c))
    );
  }

  function handleNewConversation() {
    const conv = createConversation();
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
    setSidebarOpen(false);
  }

  function handleRenameConversation(id, title) {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, title } : c)));
  }

  function handleDeleteConversation(id) {
    const remaining = conversations.filter((c) => c.id !== id);
    const nextConversations = remaining.length > 0 ? remaining : [createConversation()];
    setConversations(nextConversations);
    if (active.id === id) {
      setActiveId(nextConversations[0].id);
    }
  }

  function handleClearAll() {
    const fresh = createConversation();
    setConversations([fresh]);
    setActiveId(fresh.id);
  }

  function handleExportConversation(id) {
    const conversation = conversations.find((c) => c.id === id);
    if (!conversation || conversation.messages.length === 0) return;

    const text = conversation.messages
      .map((m) => `${m.role === "user" ? "Vous" : "TechCorp AI"} :\n${m.content}`)
      .join("\n\n");

    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${conversation.title.replace(/[^\w\s-]/g, "").trim() || "conversation"}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function runAssistantReply(history, assistantMessageId) {
    setIsStreaming(true);
    setStreamingMessageId(assistantMessageId);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      let acc = "";
      await streamChat(
        history,
        (chunk) => {
          acc += chunk;
          updateActiveMessages((prev) =>
            prev.map((m) => (m.id === assistantMessageId ? { ...m, content: acc } : m))
          );
        },
        controller.signal
      );
    } catch (err) {
      if (err.name !== "AbortError") {
        updateActiveMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? {
                  ...m,
                  content:
                    "Désolé, une erreur est survenue lors de la connexion au serveur d'inférence. Vérifiez qu'Ollama est bien démarré.",
                }
              : m
          )
        );
      }
    } finally {
      setIsStreaming(false);
      setStreamingMessageId(null);
      abortRef.current = null;
    }
  }

  async function handleSend(textOverride) {
    const text = (textOverride ?? input).trim();
    if (!text || isStreaming) return;

    const userMessage = createMessage("user", text);
    const assistantMessage = createMessage("assistant", "");
    const nextMessages = [...messages, userMessage];

    updateActiveMessages(() => [...nextMessages, assistantMessage]);
    setInput("");
    stickToBottomRef.current = true;
    setShowScrollButton(false);

    setConversations((prev) =>
      prev.map((c) =>
        c.id === active.id && c.title === DEFAULT_TITLE
          ? { ...c, title: text.slice(0, 36) + (text.length > 36 ? "…" : "") }
          : c
      )
    );

    await runAssistantReply(nextMessages, assistantMessage.id);
  }

  async function handleRegenerate(messageId) {
    if (isStreaming) return;
    const index = messages.findIndex((m) => m.id === messageId);
    if (index === -1) return;

    const history = messages.slice(0, index);
    const newMessage = createMessage("assistant", "");

    updateActiveMessages((prev) => {
      const copy = [...prev];
      copy.splice(index + 1, 0, newMessage);
      return copy;
    });

    await runAssistantReply(history, newMessage.id);
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        activeId={active.id}
        onSelect={(id) => {
          setActiveId(id);
          setSidebarOpen(false);
        }}
        onNew={handleNewConversation}
        onRename={handleRenameConversation}
        onDelete={handleDeleteConversation}
        onClearAll={handleClearAll}
        onExport={handleExportConversation}
        theme={theme}
        onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
        status={status}
        model={OLLAMA_MODEL}
        isOpen={sidebarOpen}
        collapsed={sidebarCollapsed}
        onClose={() => setSidebarOpen(false)}
        onCollapse={() => setSidebarCollapsed(true)}
      />

      <div className="main">
        <header className="topbar">
          <button
            type="button"
            className={`icon-btn topbar__menu ${sidebarCollapsed ? "topbar__menu--visible" : ""}`}
            onClick={() => {
              setSidebarOpen(true);
              setSidebarCollapsed(false);
            }}
            aria-label="Afficher le menu"
          >
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>

          <span className="topbar__brand">TechCorp AI</span>

          <div className={`status-pill status-pill--${status}`}>
            <span className={`status-dot status-dot--${status}`} />
            {status === "online" && "Connecté"}
            {status === "offline" && "Hors ligne"}
            {status === "checking" && "Connexion…"}
          </div>
        </header>

        {isEmpty ? (
          <div className="hero" key={active.id}>
            <h1 className="hero__title">
              <span className="hero__title-gradient">{greeting}</span>
            </h1>

            <div className="hero__composer">
              <ChatInput value={input} onChange={setInput} onSend={() => handleSend()} disabled={isStreaming} autoFocus />
            </div>

            <div className="suggestions suggestions--hero">
              {SUGGESTIONS.map((s) => (
                <button key={s} type="button" className="suggestion-chip" onClick={() => handleSend(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            <main className="chat" ref={scrollRef}>
              <div className="chat__inner">
                {messages.map((m) => (
                  <ChatMessage
                    key={m.id}
                    id={m.id}
                    role={m.role}
                    content={m.content}
                    isStreaming={streamingMessageId === m.id}
                    onRegenerate={m.role === "assistant" ? handleRegenerate : undefined}
                    regenerateDisabled={isStreaming}
                  />
                ))}
              </div>

              {showScrollButton && (
                <button
                  type="button"
                  className="scroll-bottom-btn"
                  onClick={() => scrollToBottom()}
                  aria-label="Revenir en bas"
                >
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 5v14M5 12l7 7 7-7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              )}
            </main>

            <footer className="composer">
              <div className="composer__inner">
                <ChatInput value={input} onChange={setInput} onSend={() => handleSend()} disabled={isStreaming} />
                {isStreaming && (
                  <button type="button" className="stop-button" onClick={handleStop}>
                    Arrêter la génération
                  </button>
                )}
                <p className="composer__hint">
                  Les réponses sont générées par IA et peuvent contenir des erreurs. Vérifiez les informations
                  financières sensibles.
                </p>
              </div>
            </footer>
          </>
        )}
      </div>
    </div>
  );
}
