import type { Metadata } from "next";
import { Playfair_Display, Inter } from "next/font/google";
import "./globals.css";
import { SITE } from "@/lib/config";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["500", "600", "700"],
  display: "swap",
});

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const title = "Recherche de véhicule sur mesure | MI LOC";
const description =
  "Confiez votre recherche automobile à MI LOC. Indiquez votre véhicule, votre budget et vos critères, et notre équipe vous accompagne dans votre recherche.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE.baseUrl),
  title: {
    default: title,
    template: `%s | ${SITE.name}`,
  },
  description,
  keywords: [
    "recherche véhicule",
    "mandataire automobile",
    "achat voiture sur mesure",
    "MI LOC",
    "recherche voiture occasion",
  ],
  authors: [{ name: SITE.name }],
  openGraph: {
    type: "website",
    locale: "fr_FR",
    siteName: SITE.name,
    title,
    description,
  },
  twitter: {
    card: "summary_large_image",
    title,
    description,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className={`${playfair.variable} ${inter.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
