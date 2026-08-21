import { Truck, ShieldCheck, Gift, BadgeDollarSign } from "lucide-react";

// "Easy Exchange / 3-day policy" removed — not yet founder-confirmed (see
// CLAUDE.md: never invent policy details). Replaced with a neutral line drawn
// from the Brand Book's Presentation pillar, not a policy promise. The real
// exchange-policy copy lives in Footer's "Returns & Exchange" link (StaticPage,
// admin-configurable) and is untouched here.
const badges = [
  { icon: BadgeDollarSign, title: "Cash on Delivery", text: "Pay when you receive your order" },
  { icon: ShieldCheck, title: "Quality Checked", text: "Every item checked before dispatch" },
  { icon: Truck, title: "Fast Delivery", text: "Across Bangladesh, 1–5 days" },
  { icon: Gift, title: "Considered Presentation", text: "Arrives ready to gift, even to yourself" },
];

export default function TrustBadges() {
  return (
    <div data-testid="trust-badges" className="grid grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
      {badges.map((b) => (
        <div
          key={b.title}
          className="flex flex-col items-center text-center p-5 md:p-6 bg-aayna-mist border border-aayna-beige rounded-sm"
        >
          <span className="h-12 w-12 rounded-full bg-white flex items-center justify-center mb-3 border border-aayna-beige">
            <b.icon className="h-5 w-5 text-aayna-burgundy" />
          </span>
          <h3 className="font-body font-semibold text-sm md:text-base text-aayna-charcoal">{b.title}</h3>
          <p className="text-xs md:text-sm text-aayna-taupe mt-1 leading-snug">{b.text}</p>
        </div>
      ))}
    </div>
  );
}
