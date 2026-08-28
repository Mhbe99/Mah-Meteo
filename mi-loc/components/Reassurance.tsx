import Reveal from "./Reveal";

const ITEMS = [
  {
    title: "Recherche personnalisée",
    description: "Nous recherchons selon vos critères et votre budget.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M10.5 18a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15Zm10.5 3-4.85-4.85"
      />
    ),
  },
  {
    title: "Accompagnement",
    description: "Un interlocuteur MI LOC échange directement avec vous.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M8 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm8 0a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2 20c.5-3 3-5 6-5s5.5 2 6 5m2-6c2.4.3 4.3 2 4.8 5"
      />
    ),
  },
  {
    title: "Transparence",
    description: "La commission est annoncée avant le début de la recherche.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M12 3v18m5-14H9.5a2.5 2.5 0 0 0 0 5h5a2.5 2.5 0 0 1 0 5H7"
      />
    ),
  },
  {
    title: "Sans engagement initial",
    description: "Vous validez les conditions avant que nous commencions la prestation.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M12 2 4 5.5v6c0 5 3.4 8.9 8 10.5 4.6-1.6 8-5.5 8-10.5v-6L12 2Zm-2.75 9.75 2 2 4-4.5"
      />
    ),
  },
];

export default function Reassurance() {
  return (
    <section className="bg-white py-24 sm:py-28">
      <div className="mx-auto max-w-content px-5 sm:px-8">
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {ITEMS.map((item, index) => (
            <Reveal key={item.title} delay={index * 80}>
              <div className="h-full rounded-xl2 border border-black/5 bg-cream/60 p-7">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  className="h-8 w-8 text-gold-dark"
                  aria-hidden
                >
                  {item.icon}
                </svg>
                <h3 className="mt-5 font-display text-base font-semibold text-ink">
                  {item.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-anthracite/70">
                  {item.description}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
