import type { ReactNode } from "react";
import Header from "./Header";
import Footer from "./Footer";

export default function LegalPageLayout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <>
      <Header />
      <main className="bg-white pb-24 pt-32 sm:pt-40">
        <div className="mx-auto max-w-3xl px-5 sm:px-8">
          <h1 className="font-display text-3xl font-semibold text-ink sm:text-4xl">{title}</h1>
          <div className="prose-mi-loc mt-8 space-y-5 text-sm leading-relaxed text-anthracite/80">
            {children}
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
