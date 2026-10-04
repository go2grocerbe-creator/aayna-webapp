import "@/App.css";

const categories = [
  { name: "Earrings", mark: "E", line: "Light at the edge of the face." },
  { name: "Necklaces", mark: "N", line: "A quiet centre of attention." },
  { name: "Rings", mark: "R", line: "Small details. Strong presence." },
];

export default function App() {
  return (
    <div className="min-h-screen bg-aayna-cream text-aayna-charcoal overflow-x-hidden">
      <header className="fixed inset-x-0 top-0 z-50 bg-aayna-cream/95 backdrop-blur border-b border-aayna-beige/70">
        <div className="h-[68px] px-5 flex items-center justify-between max-w-7xl mx-auto">
          <span className="font-display text-[25px] font-semibold text-aayna-burgundy tracking-[0.12em]">AAYNA</span>
          <a href="#mirror" className="text-[11px] uppercase tracking-[0.18em] text-aayna-burgundy font-semibold">The Edit</a>
        </div>
      </header>

      <main>
        <section className="relative min-h-[100svh] px-5 pt-[120px] pb-14 flex flex-col justify-between">
          <div aria-hidden="true" className="absolute -right-28 top-24 w-72 h-72 rounded-full border border-aayna-burgundy/10" />
          <div aria-hidden="true" className="absolute -right-16 top-36 w-48 h-48 rounded-full border border-aayna-coral/10" />
          <div className="relative z-10">
            <p className="text-[10px] font-bold tracking-[0.25em] uppercase text-aayna-coral-dark">Jewellery · Bangladesh</p>
            <h1 className="font-display mt-8 font-semibold leading-[0.88] tracking-[-0.045em]">
              <span className="block text-[15vw] sm:text-7xl text-aayna-charcoal">Reflect</span>
              <span className="block text-[15vw] sm:text-7xl text-aayna-charcoal">Your</span>
              <span className="block text-[20vw] sm:text-8xl text-aayna-burgundy italic -ml-1">Aura.</span>
            </h1>
            <p className="mt-8 max-w-[310px] text-[15px] leading-6 text-aayna-taupe">
              Modern adornment with a Bangladeshi point of view — expressive, feminine and made for everyday ritual.
            </p>
          </div>
          <div className="relative z-10 flex items-end justify-between mt-14">
            <a href="#mirror" className="inline-flex items-center gap-3 text-sm font-semibold text-aayna-burgundy border-b border-aayna-burgundy pb-1">
              Enter the mirror <span>↓</span>
            </a>
            <span className="font-bangla text-4xl text-aayna-burgundy/15">আয়না</span>
          </div>
        </section>

        <section id="mirror" className="px-5 py-20 border-t border-aayna-beige">
          <p className="text-[10px] font-bold tracking-[0.25em] uppercase text-aayna-coral-dark">The Digital Mirror</p>
          <h2 className="font-display mt-4 text-[39px] leading-[1.02] font-semibold text-aayna-burgundy-dark max-w-sm">
            What are you drawn to today?
          </h2>
          <p className="font-display italic mt-4 text-aayna-taupe text-sm">A mirror doesn't create you. It reveals you.</p>

          <div className="mt-12 border-t border-aayna-beige">
            {categories.map((c, i) => (
              <div key={c.name} className="relative py-7 border-b border-aayna-beige flex items-center justify-between gap-5">
                <div>
                  <p className="font-display text-[34px] leading-none text-aayna-charcoal">{c.name}</p>
                  <p className="mt-2 text-xs text-aayna-taupe">{c.line}</p>
                </div>
                <span className="font-display text-[64px] leading-none text-aayna-burgundy/[0.08]">{c.mark}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-5 mb-5 bg-aayna-burgundy text-aayna-cream px-6 py-12">
          <p className="text-[10px] tracking-[0.22em] uppercase text-aayna-beige">AAYNA</p>
          <p className="font-display text-4xl leading-tight mt-3">Your reflection,<br/><span className="italic text-aayna-gold">your edit.</span></p>
          <p className="text-sm leading-6 text-aayna-beige/80 mt-5">A new jewellery experience is taking shape in Bangladesh.</p>
        </section>
      </main>

      <footer className="px-5 py-8 flex justify-between items-center text-[11px] text-aayna-taupe">
        <span>© 2026 AAYNA</span><span>Reflect Your Aura.</span>
      </footer>
    </div>
  );
}
