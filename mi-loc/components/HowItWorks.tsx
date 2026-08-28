import Reveal from "./Reveal";

const STEPS = [
  {
    number: "01",
    title: "Vous nous décrivez votre recherche",
    description: "Modèle, budget, année, kilométrage, carburant, options, etc.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M9 12h6m-6 4h6M7 4h10a2 2 0 0 1 2 2v13.5a.5.5 0 0 1-.777.416L14 17l-4.223 2.916A.5.5 0 0 1 9 19.5V6a2 2 0 0 1-2-2Zm0 0a2 2 0 0 0-2 2v0"
      />
    ),
  },
  {
    number: "02",
    title: "Nous recherchons",
    description: "MI LOC recherche des véhicules correspondant à vos critères.",
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
    number: "03",
    title: "Nous vous présentons les opportunités",
    description: "Nous vous transmettons les véhicules sélectionnés et échangeons avec vous.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="M3 5.5A2.5 2.5 0 0 1 5.5 3h13A2.5 2.5 0 0 1 21 5.5v8a2.5 2.5 0 0 1-2.5 2.5H9l-5 4v-4H5.5A2.5 2.5 0 0 1 3 13.5Z"
      />
    ),
  },
  {
    number: "04",
    title: "Vous choisissez",
    description: "Si une proposition vous convient, nous vous accompagnons dans la suite de la démarche.",
    icon: (
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={1.5}
        d="m4.5 12.75 6 6 9-13.5"
      />
    ),
  },
];

export default function HowItWorks() {
  return (
    <section id="comment-ca-marche" className="bg-white py-24 sm:py-28">
      <div className="mx-auto max-w-content px-5 sm:px-8">
        <Reveal>
          <div className="mx-auto max-w-2xl text-center">
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-gold-dark">
              Notre méthode
            </p>
            <h2 className="mt-3 font-display text-3xl font-semibold text-ink sm:text-4xl">
              Comment ça marche ?
            </h2>
          </div>
        </Reveal>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <Reveal key={step.number} delay={index * 80}>
              <div className="h-full rounded-xl2 border border-black/5 bg-white p-7 shadow-card transition-shadow hover:shadow-premium">
                <div className="flex items-center justify-between">
                  <span className="font-display text-3xl font-semibold text-gold/40">
                    {step.number}
                  </span>
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    className="h-9 w-9 text-gold-dark"
                    aria-hidden
                  >
                    {step.icon}
                  </svg>
                </div>
                <h3 className="mt-6 font-display text-lg font-semibold text-ink">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-anthracite/70">
                  {step.description}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={320}>
          <p className="mt-12 text-center text-sm font-medium text-anthracite/60">
            Vous restez libre d&apos;accepter ou non les véhicules proposés.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
