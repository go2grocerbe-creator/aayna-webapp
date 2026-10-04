import { Gem } from "lucide-react";

// Reusable graceful product-image treatment (Visual QA Fix Sprint item 3).
// Never shows a browser broken-image icon and never lets alt text render as
// the visible placeholder - if there's no src, or the src fails to load, a
// quiet Mirror-Ivory/mist panel with a small gem mark shows instead. The
// real alt text stays on the <img> for screen readers either way.
export default function ProductImage({ src, alt, className = "", imgClassName = "", iconClassName = "h-6 w-6", eager = false, testId }) {
  return (
    <div className={`relative bg-aayna-cream overflow-hidden flex items-center justify-center ${className}`}>
      <Gem className={`${iconClassName} text-aayna-burgundy/30 absolute`} aria-hidden="true" />
      {src && (
        <img
          data-testid={testId}
          src={src}
          alt={alt || ""}
          loading={eager ? "eager" : "lazy"}
          className={`relative w-full h-full object-cover ${imgClassName}`}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      )}
    </div>
  );
}
