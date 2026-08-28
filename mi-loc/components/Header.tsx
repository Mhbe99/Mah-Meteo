"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

const NAV_LINKS = [
  { href: "#comment-ca-marche", label: "Comment ça marche" },
  { href: "#commission", label: "Commission" },
  { href: "#faq", label: "FAQ" },
];

export default function Header() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-white/95 shadow-card backdrop-blur" : "bg-white/0"
      }`}
    >
      <div className="mx-auto flex max-w-content items-center justify-between px-5 py-3 sm:px-8">
        <a href="#top" className="flex items-center gap-2">
          <Image
            src="/logo-mark.png"
            alt="MI LOC"
            width={160}
            height={80}
            priority
            className="h-10 w-auto sm:h-11"
          />
        </a>

        <nav className="hidden items-center gap-8 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="text-sm font-medium tracking-wide text-ink/80 transition-colors hover:text-gold-dark"
            >
              {link.label}
            </a>
          ))}
        </nav>

        <a
          href="#formulaire"
          className="rounded-full bg-ink px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-gold-dark"
        >
          Faire une demande
        </a>
      </div>
    </header>
  );
}
