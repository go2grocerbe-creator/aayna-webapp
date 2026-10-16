import { Gem } from "lucide-react";

// Reusable graceful product-image treatment (Visual QA Fix Sprint item 3).
// Never shows a browser broken-image icon and never lets alt text render as
// the visible placeholder - if there's no src, or the src fails to load, a
// quiet mist panel with a small gem mark shows instead (mist, not page
// cream, so a missing photo still reads as an image frame, not empty space). The
// real alt text stays on the <img> for screen readers either way.
// `fit="contain"` shows the whole photo inside the frame (no cropping) on the mist
// background; the default `cover` fills the frame (used by grid cards).
// `srcSet`/`sizes` let the browser pick the 480w or 1200w rendition of a static photo.
export default function ProductImage({ src, srcSet, sizes, alt, className = "", imgClassName = "", iconClassName = "h-6 w-6", eager = false, testId, fit = "cover" }) {
  // Callers often pass `absolute inset-0` to fill an aspect-ratio box. Adding
  // `relative` as well would win in Tailwind's CSS order, cancel inset-0 and
  // collapse the frame to 0px whenever the photo fails - so only default to
  // `relative` when the caller hasn't positioned the frame itself.
  const position = /\b(absolute|fixed|sticky)\b/.test(className) ? "" : "relative";
  return (
    <div className={`${position} bg-aayna-mist overflow-hidden flex items-center justify-center ${className}`}>
      <Gem className={`${iconClassName} text-aayna-burgundy/30 absolute`} aria-hidden="true" />
      {src && (
        <img
          data-testid={testId}
          src={src}
          srcSet={srcSet || undefined}
          sizes={srcSet ? sizes || "100vw" : undefined}
          alt={alt || ""}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          className={`relative w-full h-full ${fit === "contain" ? "object-contain" : "object-cover"} ${imgClassName}`}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      )}
    </div>
  );
}
