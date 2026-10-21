// The founder-approved AAYNA logo (original designer files, 21 Oct 2026). The originals are kept
// byte-for-byte in /public/brand/original/; the 180/360/720 px files are plain resized copies for
// the web (no cropping, recolouring or other edits). Logos are immutable build assets: there is
// no admin upload for them until a persistent store is configured.
//   variant="default" - burgundy frame + gold letters, for light backgrounds
//   variant="golden"  - all-gold version, for the dark burgundy footer
export default function BrandLogo({ variant = "default", className = "h-10 w-auto", alt = "AAYNA", ...rest }) {
  const name = variant === "golden" ? "aayna-logo-golden" : "aayna-logo";
  const base = `${process.env.PUBLIC_URL || ""}/brand/${name}`;
  return (
    <img
      src={`${base}-360.png`}
      srcSet={`${base}-180.png 180w, ${base}-360.png 360w, ${base}-720.png 720w`}
      sizes="(min-width: 768px) 104px, 87px"
      width="360"
      height="200"
      alt={alt}
      decoding="async"
      className={className}
      {...rest}
    />
  );
}
