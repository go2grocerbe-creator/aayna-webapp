import { STATIC_PAGES } from "@/data/staticPages";
import { useSeo } from "@/lib/seo";
import { useSettings } from "@/hooks/useStore";
import { formatBDT } from "@/lib/format";

export default function StaticPage({ pageKey }) {
  const page = STATIC_PAGES[pageKey];
  const { data: settings } = useSettings();
  useSeo({ title: page?.title, description: page?.intro });
  if (!page) return null;

  // Delivery charges are never duplicated as static text (see staticPages.js
  // comment) — inject the live section here from the same settings Checkout
  // actually charges, so this page can't drift out of sync with a real order.
  let sections = page.sections;
  if (pageKey === "delivery" && settings) {
    const chargeSection = {
      heading: "Delivery Charges",
      list: [
        `Inside Dhaka: ${formatBDT(settings.delivery_charge_inside_dhaka)}`,
        `Outside Dhaka: ${formatBDT(settings.delivery_charge_outside_dhaka)}`,
      ],
    };
    sections = [sections[0], chargeSection, ...sections.slice(1)];
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
      <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">{page.title}</h1>
      <p className="text-aayna-taupe mt-3 text-base md:text-lg leading-relaxed">{page.intro}</p>

      <div className="mt-10 space-y-8">
        {sections.map((s, i) => (
          <section key={i}>
            <h2 className="font-display text-2xl font-bold text-aayna-charcoal mb-3">{s.heading}</h2>
            {s.body && <p className="text-aayna-taupe leading-relaxed">{s.body}</p>}
            {s.list && (
              <ul className="mt-2 space-y-2">
                {s.list.map((item, j) => (
                  <li key={j} className="flex items-start gap-2.5 text-aayna-taupe">
                    <span className="h-1.5 w-1.5 rounded-full bg-aayna-burgundy mt-2 flex-shrink-0" />
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
