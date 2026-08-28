import Image from "next/image";

export default function Hero() {
  return (
    <section
      id="top"
      className="relative overflow-hidden bg-ink pb-24 pt-32 text-white sm:pb-32 sm:pt-40"
    >
      {/* Texture de fond discrète : grille + halo doré, sans image automobile surchargée */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            "linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)",
          backgroundSize: "56px 56px",
        }}
        aria-hidden
      />
      <div
        className="pointer-events-none absolute left-1/2 top-0 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-gold/20 blur-[140px]"
        aria-hidden
      />

      <div className="relative mx-auto flex max-w-content flex-col items-center px-5 text-center sm:px-8">
        <div className="rounded-2xl bg-cream/95 px-8 py-6 shadow-premium sm:px-12 sm:py-8">
          <Image
            src="/logo-full.png"
            alt="MI LOC — Mobilité & Location"
            width={340}
            height={340}
            priority
            className="h-32 w-auto sm:h-40"
          />
        </div>

        <h1 className="mt-10 max-w-3xl font-display text-4xl font-semibold leading-[1.15] sm:text-5xl md:text-6xl">
          Vous cherchez une voiture ?
          <br />
          <span className="text-gold-light">MI LOC la trouve pour vous.</span>
        </h1>

        <p className="mt-6 max-w-xl text-balance text-base leading-relaxed text-white/75 sm:text-lg">
          Décrivez-nous le véhicule que vous recherchez, votre budget et vos critères. Notre
          équipe se charge de rechercher les meilleures opportunités pour vous.
        </p>

        <a
          href="#formulaire"
          className="mt-10 inline-flex items-center justify-center rounded-full bg-gold px-9 py-4 text-base font-semibold text-ink shadow-premium transition-all hover:-translate-y-0.5 hover:bg-gold-light"
        >
          Faire une demande
        </a>
      </div>
    </section>
  );
}
