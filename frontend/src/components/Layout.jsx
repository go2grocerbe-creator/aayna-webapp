import { Outlet, useLocation } from "react-router-dom";
import { Wrench } from "lucide-react";
import AnnouncementBar from "@/components/AnnouncementBar";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import WhatsAppFloat from "@/components/WhatsAppFloat";
import { useSettings } from "@/hooks/useStore";
import { useJsonLd } from "@/lib/seo";
import { isPlaceholder } from "@/lib/format";

function MaintenanceScreen({ settings }) {
  return (
    <div data-testid="maintenance-screen" className="min-h-screen flex flex-col items-center justify-center bg-aayna-cream px-6 text-center">
      <div className="h-16 w-16 rounded-full bg-aayna-mist flex items-center justify-center mb-6">
        <Wrench className="h-8 w-8 text-aayna-burgundy" />
      </div>
      <span className="font-display text-3xl md:text-4xl font-extrabold text-aayna-charcoal tracking-tight">
        {settings?.brand_name || "AAYNA"}
      </span>
      <h1 className="font-display text-2xl md:text-3xl font-bold text-aayna-charcoal mt-6">We'll be right back</h1>
      <p className="text-aayna-taupe mt-3 max-w-md">
        Our store is briefly down for maintenance. Please check back soon — thank you for your patience.
      </p>
      {settings?.whatsapp_number && (
        <p className="text-sm text-aayna-taupe mt-6">
          Need help? Message us on WhatsApp at <span className="font-medium text-aayna-charcoal">{settings.whatsapp_number}</span>.
        </p>
      )}
    </div>
  );
}

export default function Layout() {
  const { data: settings } = useSettings();
  const location = useLocation();
  // PDP renders a sticky mobile Add to Cart bar (ProductDetail.jsx, md:hidden);
  // the floating WhatsApp button must clear it rather than sit on top.
  const hasStickyCommerceBar = location.pathname.startsWith("/product/");

  const origin = typeof window !== "undefined" ? window.location.origin : "";
  // L4: site-wide Organization + WebSite schema. Only real, already-approved
  // fields - no invented legal name, address, phone, email, or founding date.
  // Instagram/Facebook are real launch-approved links (LAUNCH_SETTINGS_BASELINE.md);
  // TikTok is deliberately excluded, matching L3.1's launch decision to keep it
  // unsurfaced. SearchAction target is the real, working /shop?search= flow.
  const sameAs = [settings?.instagram_url, settings?.facebook_url].filter(
    (u) => u && !isPlaceholder(u)
  );
  useJsonLd("organization", {
    "@context": "https://schema.org",
    "@type": "Organization",
    name: "AAYNA",
    url: origin + "/",
    logo: origin + "/favicon.svg",
    ...(sameAs.length ? { sameAs } : {}),
  });
  useJsonLd("website", {
    "@context": "https://schema.org",
    "@type": "WebSite",
    name: "AAYNA",
    url: origin + "/",
    potentialAction: {
      "@type": "SearchAction",
      target: `${origin}/shop?search={search_term_string}`,
      "query-input": "required name=search_term_string",
    },
  });

  if (settings?.maintenance_mode) {
    return <MaintenanceScreen settings={settings} />;
  }

  return (
    <>
      <AnnouncementBar />
      <Header />
      <main className="min-h-[60vh]">
        <Outlet />
      </main>
      <Footer />
      <WhatsAppFloat clearStickyBar={hasStickyCommerceBar} />
    </>
  );
}
