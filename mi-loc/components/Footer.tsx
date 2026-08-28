import Link from "next/link";
import { CONTACT, LEGAL_LINKS, SITE, SOCIAL_LINKS } from "@/lib/config";

export default function Footer() {
  const year = new Date().getFullYear();
  const hasSocial = Object.values(SOCIAL_LINKS).some(Boolean);

  return (
    <footer className="bg-ink text-white">
      <div className="mx-auto max-w-content px-5 py-16 sm:px-8">
        <div className="grid gap-12 sm:grid-cols-2 lg:grid-cols-4">
          <div className="lg:col-span-2">
            <p className="font-display text-2xl font-semibold text-white">{SITE.name}</p>
            <p className="mt-2 text-sm tracking-wide text-gold-light">{SITE.tagline}</p>
            <p className="mt-5 max-w-sm text-sm leading-relaxed text-white/60">
              Location • Recherche automobile • Achat / Revente • Services automobiles
            </p>
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/50">
              Coordonnées
            </p>
            <ul className="mt-4 space-y-2 text-sm text-white/70">
              {CONTACT.phoneDisplay && (
                <li>
                  <a href={`tel:${CONTACT.phoneHref}`} className="hover:text-gold-light">
                    {CONTACT.phoneDisplay}
                  </a>
                </li>
              )}
              {CONTACT.email && (
                <li>
                  <a href={`mailto:${CONTACT.email}`} className="hover:text-gold-light">
                    {CONTACT.email}
                  </a>
                </li>
              )}
              {CONTACT.address && <li>{CONTACT.address}</li>}
              {!CONTACT.phoneDisplay && !CONTACT.email && !CONTACT.address && (
                <li className="text-white/40">Coordonnées communiquées prochainement.</li>
              )}
            </ul>

            {hasSocial && (
              <div className="mt-5 flex gap-4">
                {SOCIAL_LINKS.instagram && (
                  <a
                    href={SOCIAL_LINKS.instagram}
                    className="text-sm text-white/60 hover:text-gold-light"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Instagram
                  </a>
                )}
                {SOCIAL_LINKS.facebook && (
                  <a
                    href={SOCIAL_LINKS.facebook}
                    className="text-sm text-white/60 hover:text-gold-light"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Facebook
                  </a>
                )}
                {SOCIAL_LINKS.linkedin && (
                  <a
                    href={SOCIAL_LINKS.linkedin}
                    className="text-sm text-white/60 hover:text-gold-light"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    LinkedIn
                  </a>
                )}
              </div>
            )}
          </div>

          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/50">
              Informations
            </p>
            <ul className="mt-4 space-y-2 text-sm text-white/70">
              <li>
                <Link href={LEGAL_LINKS.mentionsLegales} className="hover:text-gold-light">
                  Mentions légales
                </Link>
              </li>
              <li>
                <Link href={LEGAL_LINKS.confidentialite} className="hover:text-gold-light">
                  Politique de confidentialité
                </Link>
              </li>
              <li>
                <Link href={LEGAL_LINKS.contact} className="hover:text-gold-light">
                  Contact
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-14 border-t border-white/10 pt-6 text-xs text-white/40">
          © {year} {SITE.name}. Tous droits réservés.
          {CONTACT.siren ? ` — ${CONTACT.siren}` : ""}
        </div>
      </div>
    </footer>
  );
}
