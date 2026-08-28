import type { Metadata } from "next";
import Link from "next/link";
import LegalPageLayout from "@/components/LegalPageLayout";
import { CONTACT, SITE } from "@/lib/config";

export const metadata: Metadata = {
  title: "Mentions légales",
  description: `Mentions légales du site ${SITE.name}.`,
};

export default function MentionsLegalesPage() {
  return (
    <LegalPageLayout title="Mentions légales">
      <p>
        Cette page sera complétée avec les informations légales de {SITE.name}
        {CONTACT.siren ? ` (${CONTACT.siren})` : ""} : identité de l&apos;éditeur, hébergeur du
        site, directeur de publication et coordonnées de contact.
      </p>
      <p>
        En attendant la mise à jour de ces informations, vous pouvez nous contacter via le
        formulaire de recherche de véhicule ou la page{" "}
        <Link href="/contact" className="text-gold-dark underline underline-offset-4">
          Contact
        </Link>
        .
      </p>
    </LegalPageLayout>
  );
}
