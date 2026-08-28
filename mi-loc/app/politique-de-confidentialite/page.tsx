import type { Metadata } from "next";
import Link from "next/link";
import LegalPageLayout from "@/components/LegalPageLayout";
import { SITE } from "@/lib/config";

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description: `Politique de confidentialité du site ${SITE.name}.`,
};

export default function PolitiqueConfidentialitePage() {
  return (
    <LegalPageLayout title="Politique de confidentialité">
      <p>
        Les informations transmises via le formulaire de recherche de véhicule (coordonnées et
        critères de recherche) sont utilisées par {SITE.name} exclusivement afin de traiter votre
        demande, effectuer les recherches correspondantes et vous recontacter à ce sujet.
      </p>
      <p>
        Ces informations ne sont ni cédées, ni vendues à des tiers en dehors du strict cadre
        nécessaire à la réalisation du service demandé.
      </p>
      <p>
        Conformément à la réglementation applicable (RGPD), vous disposez d&apos;un droit
        d&apos;accès, de rectification, d&apos;effacement et d&apos;opposition concernant vos
        données personnelles. Pour exercer ces droits, contactez-nous via la page{" "}
        <Link href="/contact" className="text-gold-dark underline underline-offset-4">
          Contact
        </Link>
        .
      </p>
      <p className="text-anthracite/60">
        Cette page sera complétée avec l&apos;ensemble des mentions RGPD requises (durée de
        conservation, base légale, coordonnées du délégué à la protection des données le cas
        échéant, etc.).
      </p>
    </LegalPageLayout>
  );
}
