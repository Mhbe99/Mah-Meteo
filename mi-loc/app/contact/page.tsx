import type { Metadata } from "next";
import Link from "next/link";
import LegalPageLayout from "@/components/LegalPageLayout";
import { CONTACT, SITE } from "@/lib/config";

export const metadata: Metadata = {
  title: "Contact",
  description: `Contactez ${SITE.name} pour votre recherche de véhicule.`,
};

export default function ContactPage() {
  const hasDetails = CONTACT.phoneDisplay || CONTACT.email || CONTACT.address;

  return (
    <LegalPageLayout title="Contact">
      <p>
        La façon la plus rapide de nous transmettre votre recherche reste notre{" "}
        <Link href="/#formulaire" className="text-gold-dark underline underline-offset-4">
          formulaire de recherche de véhicule
        </Link>
        . Vous pouvez également nous contacter directement :
      </p>

      {hasDetails ? (
        <ul className="space-y-2">
          {CONTACT.phoneDisplay && (
            <li>
              Téléphone :{" "}
              <a href={`tel:${CONTACT.phoneHref}`} className="text-gold-dark underline underline-offset-4">
                {CONTACT.phoneDisplay}
              </a>
            </li>
          )}
          {CONTACT.email && (
            <li>
              E-mail :{" "}
              <a href={`mailto:${CONTACT.email}`} className="text-gold-dark underline underline-offset-4">
                {CONTACT.email}
              </a>
            </li>
          )}
          {CONTACT.address && <li>Adresse : {CONTACT.address}</li>}
        </ul>
      ) : (
        <p className="text-anthracite/60">
          Nos coordonnées directes seront prochainement publiées sur cette page.
        </p>
      )}
    </LegalPageLayout>
  );
}
