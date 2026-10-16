import { useState } from "react";
import { ImageOff } from "lucide-react";

// Admin image thumbnail: never shows the browser's broken-image icon. With no
// URL, or when the image fails to load, a neutral icon fills the frame and the
// title says why, so a missing/unreachable product photo is obvious, not ugly.
export default function AdminThumb({ src, alt = "", className = "", iconClassName = "h-4 w-4" }) {
  const [failed, setFailed] = useState(false);
  const show = src && !failed;
  return (
    <div
      className={`bg-gray-100 overflow-hidden flex items-center justify-center ${className}`}
      title={src && failed ? "Image could not be loaded" : !src ? "No image" : undefined}
    >
      {show ? (
        <img src={src} alt={alt} className="w-full h-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <ImageOff className={`${iconClassName} text-gray-400`} aria-label={src ? "Image could not be loaded" : "No image"} />
      )}
    </div>
  );
}
