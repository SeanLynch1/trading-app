import { useEffect, useRef, useState } from "react";
import { TIMEFRAMES } from "../timeframes";

const GROUPS = ["Minutes", "Hours", "Days"];

// A toolbar button showing the current interval ("5m ▾") that opens a grouped dropdown.
export default function IntervalMenu({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const current = TIMEFRAMES.find((tf) => tf.key === value);

  useEffect(() => {                                // close on a click outside the menu, or on Esc
    if (!open) return;
    const onPointer = (e) => { if (!rootRef.current.contains(e.target)) setOpen(false); };
    const onKey = (e) => {
      if (e.key === "Escape") {
        e.stopPropagation();                       // Esc closes the menu first, not full screen
        setOpen(false);
      }
    };
    document.addEventListener("pointerdown", onPointer);
    window.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      window.removeEventListener("keydown", onKey, true);
    };
  }, [open]);

  const pick = (key) => {
    setOpen(false);
    if (key !== value) onChange(key);
  };

  return (
    <div className="interval-menu" ref={rootRef}>
      <button
        type="button"
        className={`tool-button interval-button ${open ? "open" : ""}`}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Interval"
        onClick={() => setOpen((o) => !o)}
      >
        {current.short}
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
          <path d="M2 3.5 5 6.5 8 3.5" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div className="interval-dropdown" role="menu">
          {GROUPS.map((group) => (
            <div key={group} className="interval-group">
              <div className="interval-group-title">{group}</div>
              {TIMEFRAMES.filter((tf) => tf.group === group).map((tf) => (
                <button
                  key={tf.key}
                  type="button"
                  role="menuitemradio"
                  aria-checked={tf.key === value}
                  className={`interval-option ${tf.key === value ? "active" : ""}`}
                  onClick={() => pick(tf.key)}
                >
                  {tf.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
