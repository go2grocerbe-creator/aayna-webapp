import { Link } from "react-router-dom";
import { MessageCircle, Phone, Instagram, Facebook } from "lucide-react";
import { useSettings } from "@/hooks/useStore";
import { useSeo } from "@/lib/seo";
import { isPlaceholder } from "@/lib/format";

// L3.1: only ever render a contact method that actually works. Previously
// this page rendered the raw placeholder WhatsApp number ungated, and its
// wa.me link was silently broken (stripping non-digits from
// "+8801XXXXXXXXX" leaves only "8801" - every X is a letter, not a digit).
// Support email is intentionally withheld too: the founder has not
// approved a production support inbox yet, which is a launch-readiness
// decision isPlaceholder() can't express on its own (the stored value
// isn't placeholder-shaped, it just isn't approved) - see
// LAUNCH_BUSINESS_SETTINGS_AUDIT.md. If no channel is available yet, this
// page stays honest and minimal rather than inventing "WhatsApp us" /
// "Email us" copy for something that doesn't work.
export default function Contact() {
  const { data: settings } = useSettings();
  useSeo({ title: "Contact Us", description: "Get in touch with AAYNA." });

  const hasWhatsapp = !isPlaceholder(settings?.whatsapp_number);
  const waDigits = hasWhatsapp ? settings.whatsapp_number.replace(/[^0-9]/g, "") : "";

  const cards = [
    hasWhatsapp && {
      icon: MessageCircle,
      title: "WhatsApp",
      value: settings.whatsapp_number,
      href: `https://wa.me/${waDigits}`,
      cta: "Chat with us",
    },
    hasWhatsapp && {
      icon: Phone,
      title: "Call Us",
      value: settings.whatsapp_number,
      href: `tel:${settings.whatsapp_number}`,
      cta: "Call now",
    },
  ].filter(Boolean);

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
      <div className="text-center mb-10">
        <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">Get in Touch</h1>
        <p className="text-aayna-taupe mt-3 max-w-lg mx-auto">
          Questions about an order, sizing, or styling? Our team is here to help.
        </p>
      </div>

      {cards.length > 0 ? (
        <div className="grid sm:grid-cols-2 gap-4 md:gap-6">
          {cards.map((c) => (
            <a
              key={c.title}
              data-testid={`contact-${c.title.toLowerCase().replace(/\s/g, "-")}`}
              href={c.href}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white border border-aayna-beige p-6 text-center hover:border-aayna-burgundy transition-colors group"
            >
              <span className="h-12 w-12 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-3 group-hover:bg-aayna-burgundy transition-colors">
                <c.icon className="h-5 w-5 text-aayna-burgundy group-hover:text-white transition-colors" />
              </span>
              <h3 className="font-semibold text-aayna-charcoal">{c.title}</h3>
              <p className="text-sm text-aayna-taupe mt-1 break-all">{c.value}</p>
              <span className="text-sm text-aayna-burgundy font-medium mt-3 inline-block">{c.cta}</span>
            </a>
          ))}
        </div>
      ) : (
        <p data-testid="contact-no-channel" className="text-center text-aayna-taupe text-sm max-w-md mx-auto">
          We don't have a direct support channel live yet. For an existing order, use{" "}
          <Link to="/track-order" className="text-aayna-burgundy underline underline-offset-2">Track Order</Link>.
        </p>
      )}

      <div className="bg-aayna-mist border border-aayna-beige mt-8 p-6 text-center">
        <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-3">Follow AAYNA</h2>
        <p className="text-sm text-aayna-taupe mb-4">For new arrivals, styling tips, and offers.</p>
        <div className="flex items-center justify-center gap-4">
          <a href={settings?.instagram_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-aayna-charcoal hover:text-aayna-burgundy transition-colors">
            <Instagram className="h-5 w-5" /> <span className="text-sm">{settings?.instagram_handle}</span>
          </a>
          <a href={settings?.facebook_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-aayna-charcoal hover:text-aayna-burgundy transition-colors">
            <Facebook className="h-5 w-5" /> <span className="text-sm">AAYNA Bangladesh</span>
          </a>
        </div>
      </div>
    </div>
  );
}
