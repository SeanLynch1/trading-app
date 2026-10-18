import { useEffect, useRef } from "react";

const openModals = [];                            // open dialogs, newest last: Esc closes only the newest

// A dialog over the page: centred on wide screens, a sheet from the bottom on phones.
// Closes on Esc, on the ✕ button, or on a click on the dimmed background.
export default function Modal({ title, onClose, children, wide = false, level = 0 }) {
  const panelRef = useRef(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; });   // always the latest onClose, without re-running the effect below

  useEffect(() => {                               // once per dialog: live price updates re-render the page constantly
    const id = Symbol("modal");
    openModals.push(id);
    const onKey = (e) => {
      if (e.key !== "Escape" || openModals.at(-1) !== id) return;   // not the top-most dialog: ignore
      e.stopPropagation();                        // and don't let the page react to this Esc too
      closeRef.current();
    };
    window.addEventListener("keydown", onKey, true);
    panelRef.current?.focus();                    // move keyboard focus into the dialog
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";      // no page scrolling behind the dialog
    return () => {
      openModals.splice(openModals.indexOf(id), 1);
      window.removeEventListener("keydown", onKey, true);
      document.body.style.overflow = previous;
    };
  }, []);

  return (
    <div className="modal-backdrop" style={{ zIndex: 1100 + level * 10 }}
         onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div ref={panelRef} className={`modal-panel ${wide ? "wide" : ""}`} role="dialog" aria-modal="true"
           aria-label={title} tabIndex={-1}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
