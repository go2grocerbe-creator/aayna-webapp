import { useSettings } from "@/hooks/useStore";

export default function AnnouncementBar() {
  const { data: settings } = useSettings();
  const text = settings?.announcement_bar_text;
  if (!text) return null;
  return (
    <div data-testid="announcement-bar" className="bg-aayna-rose text-white text-center text-xs sm:text-sm font-medium py-2 px-4">
      {text}
    </div>
  );
}
