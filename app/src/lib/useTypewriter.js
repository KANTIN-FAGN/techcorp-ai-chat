import { useEffect, useRef, useState } from "react";

/**
 * Reveals `text` progressively, character by character, instead of jumping straight
 * to the latest streamed content. Once `enabled` has been true at least once, the
 * reveal keeps catching up even after it turns false, so the animation finishes
 * smoothly instead of snapping to the final text.
 */
export function useTypewriter(text, enabled) {
  const [displayed, setDisplayed] = useState(enabled ? "" : text);
  const hasStartedRef = useRef(enabled);
  const targetRef = useRef(text);
  const indexRef = useRef(enabled ? 0 : text.length);
  const timeoutRef = useRef(null);

  targetRef.current = text;
  if (enabled) hasStartedRef.current = true;

  useEffect(() => {
    if (!hasStartedRef.current) {
      setDisplayed(text);
      return undefined;
    }

    function tick() {
      const target = targetRef.current;
      if (indexRef.current >= target.length) return;

      const remaining = target.length - indexRef.current;
      const step = remaining > 80 ? 5 : remaining > 24 ? 2 : 1;
      indexRef.current = Math.min(target.length, indexRef.current + step);
      setDisplayed(target.slice(0, indexRef.current));
      timeoutRef.current = setTimeout(tick, 12);
    }

    clearTimeout(timeoutRef.current);
    if (indexRef.current < targetRef.current.length) {
      tick();
    }

    return () => clearTimeout(timeoutRef.current);
  }, [text, enabled]);

  return displayed;
}
