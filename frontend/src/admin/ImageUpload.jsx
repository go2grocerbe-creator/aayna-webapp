import { useState } from "react";
import { Loader2, Upload, Star, X } from "lucide-react";
import { toast } from "sonner";
import { uploadImage, fullImageUrl } from "@/admin/adminApi";

export default function ImageUpload({ images = [], onChange }) {
  const [busy, setBusy] = useState(false);

  const handle = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setBusy(true);
    try {
      const uploaded = [];
      for (const f of files) {
        const d = await uploadImage(f);
        uploaded.push({ image_url: fullImageUrl(d.url_path), alt_text: f.name, is_main: false, sort_order: 0 });
      }
      let next = [...images, ...uploaded];
      if (!next.some((i) => i.is_main) && next.length) next[0].is_main = true;
      onChange(next);
      toast.success(`${uploaded.length} image(s) uploaded`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  const setMain = (idx) => onChange(images.map((im, i) => ({ ...im, is_main: i === idx })));
  const remove = (idx) => {
    let next = images.filter((_, i) => i !== idx);
    if (next.length && !next.some((i) => i.is_main)) next[0].is_main = true;
    onChange(next);
  };

  return (
    <div>
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
        {images.map((im, idx) => (
          <div key={idx} className="relative group aspect-square border border-gray-200 rounded-md overflow-hidden bg-gray-50">
            <img src={im.image_url} alt={im.alt_text} className="w-full h-full object-cover" />
            {im.is_main && (
              <span className="absolute top-1 left-1 bg-aayna-gold text-aayna-charcoal text-[10px] font-bold px-1.5 py-0.5 rounded">Main</span>
            )}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
              {!im.is_main && (
                <button type="button" onClick={() => setMain(idx)} title="Set as main" className="bg-white rounded-full p-1.5">
                  <Star className="h-4 w-4 text-aayna-gold" />
                </button>
              )}
              <button type="button" onClick={() => remove(idx)} title="Remove" className="bg-white rounded-full p-1.5">
                <X className="h-4 w-4 text-red-600" />
              </button>
            </div>
          </div>
        ))}
        <label
          data-testid="image-upload-input"
          className="aspect-square border-2 border-dashed border-gray-300 rounded-md flex flex-col items-center justify-center cursor-pointer hover:border-aayna-rose text-gray-400 hover:text-aayna-rose transition-colors"
        >
          {busy ? <Loader2 className="h-6 w-6 animate-spin" /> : <Upload className="h-6 w-6" />}
          <span className="text-xs mt-1">Upload</span>
          <input type="file" accept="image/*" multiple className="hidden" onChange={handle} disabled={busy} />
        </label>
      </div>
      <p className="text-xs text-gray-400 mt-2">JPG, PNG or WEBP, up to 8MB. Hover an image to set it as the main photo or remove it.</p>
    </div>
  );
}
