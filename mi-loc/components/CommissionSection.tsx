import { COMMISSION_GRID } from "@/lib/config";
import Reveal from "./Reveal";

export default function CommissionSection() {
  const hasGrid = COMMISSION_GRID.length > 0;

  return (
    <section id="commission" className="bg-cream py-24 sm:py-28">
      <div className="mx-auto max-w-content px-5 sm:px-8">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-start">
          <Reveal>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.2em] text-gold-dark">
                Nos honoraires
              </p>
              <h2 className="mt-3 font-display text-3xl font-semibold text-ink sm:text-4xl">
                Un accompagnement transparent
              </h2>
              <p className="mt-5 max-w-lg text-base leading-relaxed text-anthracite/75">
                MI LOC facture une commission uniquement pour le service de recherche et
                d&apos;accompagnement. Le montant de la commission dépend notamment de
                l&apos;année et des caractéristiques du véhicule recherché.
              </p>
            </div>
          </Reveal>

          <Reveal delay={120}>
            <div className="rounded-xl2 border border-black/5 bg-white p-7 shadow-card sm:p-9">
              {hasGrid ? (
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="border-b border-black/10 text-xs font-semibold uppercase tracking-wide text-anthracite/60">
                      <th className="pb-3 pr-4">Véhicule</th>
                      <th className="pb-3">Commission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {COMMISSION_GRID.map((tier) => (
                      <tr key={tier.range} className="border-b border-black/5 last:border-0">
                        <td className="py-3 pr-4 text-sm text-ink">{tier.range}</td>
                        <td className="py-3 text-sm font-semibold text-gold-dark">
                          {tier.commission}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="text-center sm:text-left">
                  <p className="font-display text-xl font-semibold text-ink">
                    Commission communiquée avant le lancement de la recherche.
                  </p>
                </div>
              )}

              <p className="mt-6 border-t border-black/5 pt-5 text-sm font-medium text-anthracite/70">
                Aucun engagement avant validation du tarif par le client.
              </p>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
