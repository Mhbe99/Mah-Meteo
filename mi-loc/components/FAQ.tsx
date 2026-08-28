"use client";

import { useState } from "react";
import Reveal from "./Reveal";

const QUESTIONS = [
  {
    q: "Combien coûte le service MI LOC ?",
    a: "La commission dépend du véhicule recherché et vous est communiquée avant le lancement de la recherche.",
  },
  {
    q: "Suis-je obligé d'acheter un véhicule proposé ?",
    a: "Non. Vous restez libre d'accepter ou de refuser les véhicules présentés, selon les conditions définies avec MI LOC.",
  },
  {
    q: "Quels véhicules pouvez-vous rechercher ?",
    a: "MI LOC peut étudier différents types de véhicules selon votre budget et vos critères.",
  },
  {
    q: "Comment vais-je être recontacté ?",
    a: "Par téléphone, SMS, WhatsApp ou e-mail selon les coordonnées et préférences indiquées dans votre demande.",
  },
  {
    q: "Combien de temps faut-il pour trouver un véhicule ?",
    a: "Cela dépend du modèle, du budget, de l'état du marché et de vos critères.",
  },
];

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);

  return (
    <section id="faq" className="bg-cream py-24 sm:py-28">
      <div className="mx-auto max-w-content px-5 sm:px-8">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-gold-dark">
              Questions fréquentes
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-ink sm:text-4xl">FAQ</h2>
          </div>
        </Reveal>

        <Reveal delay={100}>
          <div className="mx-auto mt-12 max-w-3xl divide-y divide-black/10 rounded-xl2 border border-black/5 bg-white shadow-card">
            {QUESTIONS.map((item, index) => {
              const isOpen = openIndex === index;
              return (
                <div key={item.q}>
                  <button
                    type="button"
                    onClick={() => setOpenIndex(isOpen ? null : index)}
                    className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                    aria-expanded={isOpen}
                  >
                    <span className="font-display text-base font-semibold text-ink">
                      {item.q}
                    </span>
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.5}
                      className={`h-5 w-5 shrink-0 text-gold-dark transition-transform ${
                        isOpen ? "rotate-45" : ""
                      }`}
                      aria-hidden
                    >
                      <path strokeLinecap="round" d="M12 5v14M5 12h14" />
                    </svg>
                  </button>
                  {isOpen && (
                    <div className="px-6 pb-5 text-sm leading-relaxed text-anthracite/75">
                      {item.a}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
