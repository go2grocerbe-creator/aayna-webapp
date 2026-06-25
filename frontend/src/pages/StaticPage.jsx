import { STATIC_PAGES } from "@/data/staticPages";
import { useSeo } from "@/lib/seo";

export default function StaticPage({ pageKey }) {
  const page = STATIC_PAGES[pageKey];
  useSeo({ title: page?.title, description: page?.intro });
  if (!page) return null;

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
      <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">{page.title}</h1>
      <p className="text-aayna-taupe mt-3 text-base md:text-lg leading-relaxed">{page.intro}</p>

      <div className="mt-10 space-y-8">
        {page.sections.map((s, i) => (
          <section key={i}>
            <h2 className="font-display text-2xl font-bold text-aayna-charcoal mb-3">{s.heading}</h2>
            {s.body && <p className="text-aayna-taupe leading-relaxed">{s.body}</p>}
            {s.list && (
              <ul className="mt-2 space-y-2">
                {s.list.map((item, j) => (
                  <li key={j} className="flex items-start gap-2.5 text-aayna-taupe">
                    <span className="h-1.5 w-1.5 rounded-full bg-aayna-rose mt-2 flex-shrink-0" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
