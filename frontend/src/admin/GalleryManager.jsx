// Product photo order and cover (founder kit GalleryManager.jsx, wired to backend/gallery.py).
// The first photo is the catalogue cover on cards, the product page, cart, orders and SEO.
// Saving sends the revision it was based on; if someone else saved first the server answers 409
// and this reloads instead of overwriting. Uploads stay disabled until permanent storage exists.
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, Star, Loader2, Save, Trash2, Upload } from "lucide-react";
import { deleteProductGalleryImage, getProductGallery, saveProductGalleryOrder, uploadProductGalleryImage } from "@/admin/adminApi";

export default function GalleryManager({ productId, canEdit = true }) {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["admin-gallery", productId],
    queryFn: () => getProductGallery(productId),
    enabled: Boolean(productId),
  });
  const [ids, setIds] = useState([]);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { if (data) setIds(data.images.map((i) => i.id)); }, [data]);

  if (!productId) return null;
  if (isLoading) return <div className="py-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-aayna-burgundy" /></div>;
  if (isError || !data) return <p className="text-sm text-red-700">Could not load the photos. <button type="button" className="underline" onClick={() => refetch()}>Retry</button></p>;
  const byId = Object.fromEntries(data.images.map((i) => [i.id, i]));
  const ordered = ids.map((id) => byId[id]).filter(Boolean);
  const dirty = ids.join("|") !== data.images.map((i) => i.id).join("|");
  const editable = canEdit && data.editable;

  const move = (index, dir) => {
    const next = [...ids], other = index + dir;
    if (other < 0 || other >= next.length) return;
    [next[index], next[other]] = [next[other], next[index]];
    setIds(next);
  };
  const makeCover = (index) => { const next = [...ids]; const [x] = next.splice(index, 1); setIds([x, ...next]); };

  const save = async () => {
    setSaving(true); setError("");
    try {
      const fresh = await saveProductGalleryOrder(productId, data.revision, ids);
      qc.setQueryData(["admin-gallery", productId], fresh);
      qc.invalidateQueries({ queryKey: ["admin-product", productId] });
      qc.invalidateQueries({ queryKey: ["admin-products"] });
      toast.success("Photo order saved. The first photo is now the cover.");
    } catch (e) {
      const status = e?.response?.status;
      const msg = e?.response?.data?.detail || "Could not save the photo order.";
      setError(msg);
      if (status === 409) { await refetch(); }
    } finally { setSaving(false); }
  };

  const upload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    if (ordered.length + files.length > data.max_images) {
      setError(`A product can have at most ${data.max_images} images.`); event.target.value = ""; return;
    }
    setUploading(true); setError("");
    let revision = data.revision;
    try {
      for (const file of files) {
        const requestId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const fresh = await uploadProductGalleryImage(productId, revision, file, requestId);
        revision = fresh.revision;
        qc.setQueryData(["admin-gallery", productId], fresh);
      }
      await refetch();
      qc.invalidateQueries({ queryKey: ["admin-product", productId] });
      qc.invalidateQueries({ queryKey: ["admin-products"] });
      toast.success(`${files.length} image${files.length === 1 ? "" : "s"} uploaded.`);
    } catch (e) {
      setError(e?.response?.data?.detail || "Upload failed. Check the file and storage configuration, then retry.");
      await refetch();
    } finally { setUploading(false); event.target.value = ""; }
  };

  const remove = async (img) => {
    if (!window.confirm("Remove this uploaded image from the product? This cannot be undone.")) return;
    setSaving(true); setError("");
    try {
      const fresh = await deleteProductGalleryImage(productId, img.id, data.revision);
      qc.setQueryData(["admin-gallery", productId], fresh);
      qc.invalidateQueries({ queryKey: ["admin-product", productId] });
      if (fresh.warning) toast.warning(fresh.warning); else toast.success("Image removed.");
    } catch (e) { setError(e?.response?.data?.detail || "Could not remove the image."); await refetch(); }
    finally { setSaving(false); }
  };

  return (
    <section aria-label="Product photos" data-testid="gallery-manager" className="mb-5">
      <p className="text-sm text-gray-600 mb-3">
        {ordered.length} photo{ordered.length === 1 ? "" : "s"} for this SKU. The <strong>first photo is the cover</strong> on the
        catalogue, product page, cart and orders. Change the order, then save.
      </p>
      {error && <p role="alert" data-testid="gallery-error" className="mb-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}
      <ol className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {ordered.map((img, index) => (
          <li key={img.id} data-testid={`gallery-item-${index}`} className={`border rounded-md p-2 bg-white ${index === 0 ? "border-aayna-burgundy" : "border-gray-200"}`}>
            <img src={img.url} alt={`Photo ${index + 1}`} className="w-full aspect-[4/5] object-cover rounded" loading="lazy" />
            <p className="text-xs mt-1.5 font-medium text-gray-700">{index === 0 ? "Cover" : `Photo ${index + 1}`}</p>
            {editable && (
              <div className="flex gap-1 mt-1.5">
                <button type="button" onClick={() => move(index, -1)} disabled={saving || index === 0} aria-label={`Move photo ${index + 1} earlier`}
                        className="h-9 w-9 flex items-center justify-center border border-gray-300 rounded disabled:opacity-40"><ArrowLeft className="h-4 w-4" /></button>
                <button type="button" onClick={() => move(index, 1)} disabled={saving || index === ordered.length - 1} aria-label={`Move photo ${index + 1} later`}
                        className="h-9 w-9 flex items-center justify-center border border-gray-300 rounded disabled:opacity-40"><ArrowRight className="h-4 w-4" /></button>
                <button type="button" onClick={() => makeCover(index)} disabled={saving || index === 0} data-testid={`gallery-cover-${index}`}
                        className="h-9 px-2 flex items-center gap-1 border border-gray-300 rounded text-xs disabled:opacity-40"><Star className="h-3.5 w-3.5" /> Cover</button>
                {img.source === "r2" && <button type="button" onClick={() => remove(img)} disabled={saving || uploading}
                        aria-label={`Remove photo ${index + 1}`} className="h-9 w-9 flex items-center justify-center border border-red-200 text-red-700 rounded disabled:opacity-40"><Trash2 className="h-4 w-4" /></button>}
              </div>
            )}
          </li>
        ))}
      </ol>
      {editable && (
        <div className="mt-3 flex flex-wrap gap-3">
          <button type="button" data-testid="gallery-save" onClick={save} disabled={saving || uploading || !dirty}
                  className="h-11 px-5 bg-aayna-burgundy text-white rounded-md text-sm font-semibold disabled:opacity-50 flex items-center gap-2">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Save photo order
          </button>
          {data.uploads?.enabled && ordered.length < data.max_images && <label className="h-11 px-5 border border-gray-300 rounded-md text-sm font-semibold flex items-center gap-2 cursor-pointer">
            {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} Upload photos
            <input type="file" accept="image/jpeg,image/png,image/webp" multiple className="hidden" disabled={uploading || saving} onChange={upload} />
          </label>}
        </div>
      )}
      <p data-testid="gallery-uploads-off" className="text-xs text-gray-500 mt-3">
        {data.uploads?.enabled ? `JPEG, PNG or WebP; up to ${Math.round(data.max_upload_bytes / 1024 / 1024)} MB each and ${data.max_images} photos per product.` : `New photo uploads are unavailable: ${data.uploads?.reason || "permanent image storage is not configured."}`}
      </p>
    </section>
  );
}
