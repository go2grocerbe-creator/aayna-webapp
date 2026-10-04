import "@/App.css";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";

function DemoHome() {
  return (
    <div className="min-h-screen bg-aayna-cream text-aayna-charcoal">
      <header className="border-b border-aayna-beige px-5 md:px-10 h-20 flex items-center justify-between">
        <Link to="/" className="font-display text-3xl font-semibold text-aayna-burgundy tracking-[0.08em]">AAYNA</Link>
        <div className="text-sm text-aayna-burgundy">Reflect Your Aura.</div>
      </header>
      <main>
        <section className="min-h-[78vh] flex items-end">
          <div className="max-w-7xl mx-auto w-full px-5 md:px-10 pb-20 md:pb-28 pt-24">
            <p className="text-aayna-burgundy font-bold text-xs tracking-[0.24em] uppercase mb-5">AAYNA · Bangladesh</p>
            <h1 className="font-display font-semibold leading-[0.95] tracking-tight">
              <span className="block text-aayna-charcoal text-5xl sm:text-7xl md:text-8xl">Reflect Your</span>
              <span className="block text-aayna-burgundy text-6xl sm:text-8xl md:text-9xl mt-2">Aura.</span>
            </h1>
            <p className="mt-7 max-w-xl text-aayna-taupe text-base md:text-lg">
              Accessible premium jewellery, shaped by a modern Bangladeshi point of view.
            </p>
            <a href="#edit" className="inline-block mt-8 text-aayna-coral-dark font-semibold border-b border-aayna-coral-dark pb-1">Enter the Edit →</a>
          </div>
        </section>
        <section id="edit" className="border-t border-aayna-beige py-20">
          <div className="max-w-7xl mx-auto px-5 md:px-10">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase">The Digital Mirror</p>
            <h2 className="font-display text-4xl md:text-6xl text-aayna-burgundy mt-4">What are you drawn to today?</h2>
            <div className="mt-12 grid md:grid-cols-3 gap-4">
              {["Earrings","Necklaces","Rings"].map((x) => (
                <div key={x} className="border border-aayna-beige min-h-52 p-7 flex items-end">
                  <span className="font-display text-4xl text-aayna-charcoal">{x}</span>
                </div>
              ))}
            </div>
            <p className="mt-12 text-sm text-aayna-taupe">AAYNA · Current collection preview</p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="*" element={<DemoHome />} />
      </Routes>
    </BrowserRouter>
  );
}
