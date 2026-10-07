/**
 * Motion primitives. Each one degrades to a static render when the viewer
 * prefers reduced motion.
 */

import { useEffect, useRef, useState } from "react";
import { animate, motion, useInView, useReducedMotion } from "motion/react";

/** Fade-and-rise once when the element first scrolls into view. */
export function Reveal({ children, delay = 0, y = 14, as = "div", className, ...rest }) {
  const reduce = useReducedMotion();
  const Comp = motion[as] || motion.div;
  if (reduce) {
    const Tag = as;
    return (
      <Tag className={className} {...rest}>
        {children}
      </Tag>
    );
  }
  return (
    <Comp
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "0px 0px -8% 0px" }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      {...rest}
    >
      {children}
    </Comp>
  );
}

/**
 * Number that counts up the first time it scrolls into view. Later changes
 * (live data) apply immediately so the figure never lags behind the truth.
 */
export function CountUp({ value, decimals = 0, duration = 0.9, format, className }) {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true });
  const played = useRef(false);
  const [display, setDisplay] = useState(reduce ? value : 0);

  useEffect(() => {
    if (value === null || value === undefined || Number.isNaN(value)) {
      setDisplay(null);
      return undefined;
    }
    if (played.current || reduce) {
      setDisplay(value);
      return undefined;
    }
    if (!inView) return undefined;
    played.current = true;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(v),
      onComplete: () => setDisplay(value),
    });
    return () => {
      controls.stop();
      setDisplay(value);
    };
  }, [value, reduce, inView, duration]);

  const text = display === null || display === undefined ? "—" : format ? format(display) : Number(display).toFixed(decimals);
  return (
    <span ref={ref} className={className}>
      {text}
    </span>
  );
}

/** Element that leans slightly towards the pointer. Fine pointers only. */
export function Magnetic({ children, strength = 0.25, className }) {
  const ref = useRef(null);
  const reduce = useReducedMotion();
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const fine = typeof window !== "undefined" && window.matchMedia?.("(pointer: fine)").matches;

  if (reduce || !fine) return <span className={className}>{children}</span>;

  return (
    <motion.span
      ref={ref}
      className={className}
      style={{ display: "inline-flex" }}
      animate={{ x: offset.x, y: offset.y }}
      transition={{ type: "spring", stiffness: 260, damping: 18, mass: 0.4 }}
      onPointerMove={(e) => {
        const r = ref.current.getBoundingClientRect();
        setOffset({
          x: (e.clientX - (r.left + r.width / 2)) * strength,
          y: (e.clientY - (r.top + r.height / 2)) * strength,
        });
      }}
      onPointerLeave={() => setOffset({ x: 0, y: 0 })}
    >
      {children}
    </motion.span>
  );
}

/** Mount children only once they approach the viewport (charts animate on entry). */
export function WhenVisible({ children, minHeight = 200, className }) {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "120px 0px" });
  return (
    <div ref={ref} className={className} style={{ minHeight: inView ? undefined : minHeight }}>
      {inView ? children : null}
    </div>
  );
}
