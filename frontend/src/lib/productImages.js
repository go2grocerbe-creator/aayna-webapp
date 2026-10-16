// One rule for which photo is a product's primary image and how every photo is
// described to screen readers. Used by cards, the product page gallery and the
// cart so they never disagree.
//
// Order: the image flagged `is_main` first, then ascending `sort_order`, then the
// order stored on the product. Numbered photo variations are gallery views of
// ONE product - they are never treated as inventory variants.

const FILENAME_LIKE = /\.(png|jpe?g|webp|gif|avif)$/i;

function goodAlt(text) {
  const t = (text || "").trim();
  return t && !FILENAME_LIKE.test(t) ? t : "";
}

export function productImages(product) {
  const name = product?.product_name || "Product";
  const list = (product?.images || [])
    .map((img, i) => ({ img: img || {}, i }))
    .filter(({ img }) => typeof img.image_url === "string" && img.image_url.trim())
    .sort((a, b) =>
      (b.img.is_main ? 1 : 0) - (a.img.is_main ? 1 : 0) ||
      (Number(a.img.sort_order) || 0) - (Number(b.img.sort_order) || 0) ||
      a.i - b.i);
  const n = list.length;
  return list.map(({ img }, k) => ({
    src: img.image_url,
    alt: goodAlt(img.alt_text) || (n > 1 ? `${name} — image ${k + 1} of ${n}` : name),
  }));
}

export function primaryImage(product) {
  return productImages(product)[0] || { src: undefined, alt: product?.product_name || "" };
}
