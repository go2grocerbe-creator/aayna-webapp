import { MessageCircle, Phone, Mail, Instagram, Facebook } from "lucide-react";
import { useSettings } from "@/hooks/useStore";

export default function Contact() {
  const { data: settings } = useSettings();
  const waDigits = (settings?.whatsapp_number || "").replace(/[^0-9]/g, "");

  const cards = [
    {
      icon: MessageCircle,
      title: "WhatsApp",
      value: settings?.whatsapp_number,
      href: `https://wa.me/${waDigits}`,
      cta: "Chat with us",
    },
    {
      icon: Phone,
      title: "Call Us",
      value: settings?.whatsapp_number,
      href: `tel:${settings?.whatsapp_number}`,
      cta: "Call now",
    },
    {
      icon: Mail,
      title: "Email",
      value: settings?.support_email,
      href: `mailto:${settings?.support_email}`,
      cta: "Send email",
    },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-16">
      <div className="text-center mb-10">
        <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">Get in Touch</h1>
        <p className="text-aayna-taupe mt-3 max-w-lg mx-auto">
          Questions about an order, sizing, or styling? Our team is here to help — usually within a few hours.
        </p>
      </div>

      <div className="grid sm:grid-cols-3 gap-4 md:gap-6">
        {cards.map((c) => (
          <a
            key={c.title}
            data-testid={`contact-${c.title.toLowerCase().replace(/\s/g, "-")}`}
            href={c.href}
            target="_blank"
            rel="noopener noreferrer"
            className="bg-white border border-aayna-beige p-6 text-center hover:border-aayna-rose transition-colors group"
          >
            <span className="h-12 w-12 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-3 group-hover:bg-aayna-rose transition-colors">
              <c.icon className="h-5 w-5 text-aayna-rose group-hover:text-white transition-colors" />
            </span>
            <h3 className="font-semibold text-aayna-charcoal">{c.title}</h3>
            <p className="text-sm text-aayna-taupe mt-1 break-all">{c.value}</p>
            <span className="text-sm text-aayna-rose font-medium mt-3 inline-block">{c.cta}</span>
          </a>
        ))}
      </div>

      <div className="bg-aayna-mist border border-aayna-beige mt-8 p-6 text-center">
        <h2 className="font-display text-xl font-bold text-aayna-charcoal mb-3">Follow AAYNA</h2>
        <p className="text-sm text-aayna-taupe mb-4">For new arrivals, styling tips, and offers.</p>
        <div className="flex items-center justify-center gap-4">
          <a href={settings?.instagram_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-aayna-charcoal hover:text-aayna-rose transition-colors">
            <Instagram className="h-5 w-5" /> <span className="text-sm">{settings?.instagram_handle}</span>
          </a>
          <a href={settings?.facebook_url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-aayna-charcoal hover:text-aayna-rose transition-colors">
            <Facebook className="h-5 w-5" /> <span className="text-sm">AAYNA Bangladesh</span>
          </a>
        </div>
      </div>
    </div>
  );
}
