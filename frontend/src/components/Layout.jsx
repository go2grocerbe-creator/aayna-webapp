import { Outlet } from "react-router-dom";
import { Wrench } from "lucide-react";
import AnnouncementBar from "@/components/AnnouncementBar";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import WhatsAppFloat from "@/components/WhatsAppFloat";
import { useSettings } from "@/hooks/useStore";

function MaintenanceScreen({ settings }) {
  return (
    <div data-testid="maintenance-screen" className="min-h-screen flex flex-col items-center justify-center bg-aayna-cream px-6 text-center">
      <div className="h-16 w-16 rounded-full bg-aayna-mist flex items-center justify-center mb-6">
        <Wrench className="h-8 w-8 text-aayna-rose" />
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
      <WhatsAppFloat />
    </>
  );
}
