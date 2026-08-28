import Header from "@/components/Header";
import Hero from "@/components/Hero";
import HowItWorks from "@/components/HowItWorks";
import CommissionSection from "@/components/CommissionSection";
import SearchForm from "@/components/SearchForm";
import Reassurance from "@/components/Reassurance";
import FAQ from "@/components/FAQ";
import Footer from "@/components/Footer";

export default function HomePage() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <HowItWorks />
        <CommissionSection />
        <SearchForm />
        <Reassurance />
        <FAQ />
      </main>
      <Footer />
    </>
  );
}
