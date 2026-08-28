"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

type RevealProps = {
  children: ReactNode;
  delay?: number;
  className?: string;
};

// "pending" = état initial (SSR + premier rendu client) : toujours visible,
// pour ne jamais masquer de contenu tant que le JS n'a pas confirmé qu'une
// animation est possible. Seuls les blocs réellement sous la ligne de flottaison
// passent brièvement par "hidden" avant de s'animer à l'entrée dans l'écran.
type RevealState = "pending" | "hidden" | "visible";

export default function Reveal({ children, delay = 0, className = "" }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<RevealState>("pending");

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") {
      setState("visible");
      return;
    }

    const rect = node.getBoundingClientRect();
    const alreadyInView = rect.top < window.innerHeight && rect.bottom > 0;
    if (alreadyInView) {
      setState("visible");
      return;
    }

    setState("hidden");

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setState("visible");
          observer.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -60px 0px" },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const stateClass =
    state === "hidden" ? "opacity-0" : state === "visible" ? "animate-fade-up" : "";

  return (
    <div
      ref={ref}
      className={`${stateClass} ${className}`}
      style={state === "visible" ? { animationDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}
