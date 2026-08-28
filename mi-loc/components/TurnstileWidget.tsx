"use client";

import { useEffect, useId, useRef } from "react";

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback"?: () => void;
          theme?: "light" | "dark" | "auto";
        },
      ) => string;
      reset: (widgetId?: string) => void;
    };
    __miLocTurnstileLoading?: Promise<void>;
  }
}

const SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

function loadTurnstileScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (window.__miLocTurnstileLoading) return window.__miLocTurnstileLoading;

  window.__miLocTurnstileLoading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Impossible de charger Cloudflare Turnstile."));
    document.head.appendChild(script);
  });

  return window.__miLocTurnstileLoading;
}

type TurnstileWidgetProps = {
  siteKey: string;
  onToken: (token: string) => void;
};

export default function TurnstileWidget({ siteKey, onToken }: TurnstileWidgetProps) {
  const containerId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;

    loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return;
        window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          callback: onToken,
          theme: "light",
        });
      })
      .catch((err) => {
        console.error(err);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteKey]);

  return <div ref={containerRef} id={containerId} className="mt-2" />;
}
