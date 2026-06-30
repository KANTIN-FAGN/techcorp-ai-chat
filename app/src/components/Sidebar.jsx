import { useMemo, useState } from "react";
import ConfirmDialog from "./ConfirmDialog.jsx";
import BrandIcon from "./BrandIcon.jsx";

const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform ?? navigator.userAgent);

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onRename,
  onDelete,
  onClearAll,
  onExport,
  theme,
  onToggleTheme,
  status,
  model,
  isOpen,
  collapsed,
  onClose,
  onCollapse,
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [menuOpenId, setMenuOpenId] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState("");
  const [confirmAction, setConfirmAction] = useState(null);

  const filtered = useMemo(() => {
    if (!query.trim()) return conversations;
    const q = query.trim().toLowerCase();
    return conversations.filter((c) => c.title.toLowerCase().includes(q));
  }, [conversations, query]);

  function closeSearch() {
    setSearchOpen(false);
    setQuery("");
  }

  function startRename(conversation) {
    setEditingId(conversation.id);
    setEditValue(conversation.title);
    setMenuOpenId(null);
  }

  function commitRename(id) {
    const trimmed = editValue.trim();
    if (trimmed) onRename(id, trimmed);
    setEditingId(null);
  }

  function requestDelete(conversation) {
    setConfirmAction({ type: "delete", id: conversation.id, title: conversation.title });
    setMenuOpenId(null);
  }

  function handleConfirm() {
    if (!confirmAction) return;
    if (confirmAction.type === "delete") onDelete(confirmAction.id);
    if (confirmAction.type === "clearAll") onClearAll();
    setConfirmAction(null);
  }

  return (
    <>
      {isOpen && <div className="sidebar-scrim" onClick={onClose} />}
      <aside className={`sidebar ${isOpen ? "sidebar--open" : ""} ${collapsed ? "sidebar--collapsed" : ""}`}>
        <div className="sidebar__top">
          <button
            type="button"
            className="icon-btn icon-btn--ghost sidebar__close"
            onClick={() => {
              onClose();
              onCollapse?.();
            }}
            aria-label="Masquer le menu"
          >
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
            </svg>
          </button>
          <div className="sidebar__brand">
            <div className="brand-mark">
              <BrandIcon />
            </div>
            <span className="sidebar__brand-name">TechCorp AI</span>
          </div>
        </div>

        <button
          type="button"
          className="new-chat-btn"
          onClick={() => {
            closeSearch();
            onNew();
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
          Nouvelle conversation
          <kbd className="kbd-hint">{isMac ? "⌘K" : "Ctrl+K"}</kbd>
        </button>

        {searchOpen ? (
          <div className="search-box">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
              <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Rechercher…"
              autoFocus
              onKeyDown={(e) => e.key === "Escape" && closeSearch()}
            />
            <button type="button" className="search-box__clear" onClick={closeSearch} aria-label="Fermer la recherche">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        ) : (
          <button type="button" className="nav-item" onClick={() => setSearchOpen(true)}>
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.6" />
              <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            Rechercher dans les discussions
          </button>
        )}

        <div className="sidebar__section-label">{query.trim() ? "Résultats" : "Récentes"}</div>
        <nav className="conversation-list">
          {filtered.length === 0 && <p className="conversation-empty">Aucune conversation trouvée.</p>}
          {filtered.map((c) => (
            <div key={c.id} className="conversation-row">
              {editingId === c.id ? (
                <input
                  type="text"
                  className="conversation-edit"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onBlur={() => commitRename(c.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") commitRename(c.id);
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  autoFocus
                />
              ) : (
                <button
                  className={`conversation-item ${c.id === activeId ? "conversation-item--active" : ""}`}
                  onClick={() => onSelect(c.id)}
                  type="button"
                >
                  <span>{c.title}</span>
                </button>
              )}

              <div className="conversation-menu-wrap">
                <button
                  type="button"
                  className="conversation-menu-btn"
                  onClick={() => setMenuOpenId(menuOpenId === c.id ? null : c.id)}
                  aria-label="Options de la conversation"
                >
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="12" cy="5" r="1.4" fill="currentColor" />
                    <circle cx="12" cy="12" r="1.4" fill="currentColor" />
                    <circle cx="12" cy="19" r="1.4" fill="currentColor" />
                  </svg>
                </button>

                {menuOpenId === c.id && (
                  <>
                    <div className="menu-scrim" onClick={() => setMenuOpenId(null)} />
                    <div className="conversation-menu">
                      <button type="button" onClick={() => startRename(c)}>
                        Renommer
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          onExport(c.id);
                          setMenuOpenId(null);
                        }}
                      >
                        Exporter
                      </button>
                      <button type="button" className="conversation-menu__danger" onClick={() => requestDelete(c)}>
                        Supprimer
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}
        </nav>

        <div className="sidebar__footer">
          <button type="button" className="nav-item" onClick={onToggleTheme}>
            {theme === "dark" ? (
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.6" />
                <path
                  d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M20 14.5A8.5 8.5 0 119.5 4a7 7 0 0010.5 10.5z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
              </svg>
            )}
            {theme === "dark" ? "Mode clair" : "Mode sombre"}
          </button>

          <button
            type="button"
            className="nav-item nav-item--danger"
            onClick={() => setConfirmAction({ type: "clearAll" })}
          >
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2m-9 0l1 13a1 1 0 001 1h8a1 1 0 001-1l1-13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Effacer tout l'historique
          </button>

          <div className="model-card">
            <div className={`status-dot status-dot--${status}`} />
            <div className="model-card__text">
              <span className="model-card__name">{model}</span>
              <span className="model-card__status">
                {status === "online" && "Serveur en ligne"}
                {status === "offline" && "Serveur hors ligne"}
                {status === "checking" && "Vérification…"}
              </span>
            </div>
          </div>
        </div>
      </aside>

      <ConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.type === "clearAll" ? "Effacer tout l'historique ?" : `Supprimer "${confirmAction?.title}" ?`}
        description={
          confirmAction?.type === "clearAll"
            ? "Toutes vos conversations seront supprimées définitivement. Cette action est irréversible."
            : "Cette conversation sera supprimée définitivement. Cette action est irréversible."
        }
        confirmLabel={confirmAction?.type === "clearAll" ? "Tout effacer" : "Supprimer"}
        danger
        onConfirm={handleConfirm}
        onCancel={() => setConfirmAction(null)}
      />
    </>
  );
}
