import { useParams, Link, useNavigate } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { ChevronRight, Minus, Plus } from "lucide-react";
import { getProduct } from "@/lib/api";
import { useCart } from "@/context/CartContext";
import { useSettings } from "@/hooks/useStore";
import { formatBDT, effectivePrice, discountPercent, isOutOfStock, isPlaceholder } from "@/lib/format";
import ProductCard from "@/components/ProductCard";
import ProductImage from "@/components/ProductImage";
import { useSeo, useJsonLd } from "@/lib/seo";

// Matches the same launch-scope allowlist used by Shop.jsx/Category.jsx (D2
// "The Edit"). A product outside these categories is real catalogue, just
// not launch-promoted - noindex, not deleted or hidden from direct visitors.
const EDIT_CATEGORY_SLUGS = ["earrings", "necklaces", "rings"];

// The Object (D3, concept-d3-the-object.html). The product is the visual
// protagonist; no letterform, no scattered typography — one hairline seam
// and one quiet arc only, both far more restrained than the homepage.
//
// Every claim in this file has been re-audited against real project
// evidence (this round's explicit instruction), not carried forward just
// because the previous ProductDetail.jsx already said it:
//   - "Delivered nationwide. Cash on Delivery available" -> verified business
//     policy, links to the real delivery-policy page. Kept.
//   - "See our Returns & Exchange policy" -> verified business policy, real
//     link. Kept.
//   - "Quality checked before dispatch." -> REMOVED. It existed in the old
//     copy but no settings field, documented QC process, or founder
//     confirmation backs it this session - unsupported (Category D), not a
//     verified claim just because it shipped before.
export default function ProductDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { addItem } = useCart();
  const { data: settings } = useSettings();
  const [qty, setQty] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["product", slug],
    queryFn: () => getProduct(slug),
    retry: 1,
  });
  const product = data?.product;
  // L4: a bad/deactivated slug used to leave isLoading:false with no product
  // and no noindex — page silently stayed indexable under the default title.
  const notFound = !isLoading && (isError || !product);
  const isLaunchCategory = !!product && EDIT_CATEGORY_SLUGS.includes(product.category_slug);
  const pageUrl = typeof window !== "undefined" ? window.location.origin + window.location.pathname : "";

  useSeo({
    title: product?.product_name,
    description: product
      ? `${product.product_name}${product.category_name ? " — " + product.category_name : ""} at AAYNA, women's accessories in Bangladesh. ${product.short_description || ""} Price: ${formatBDT(effectivePrice(product))}.`.replace(/\s+/g, " ").trim()
      : undefined,
    image: product?.images?.[0]?.image_url,
    noindex: notFound ? true : !isLaunchCategory,
  });

  useJsonLd(
    "product",
    product
      ? {
          "@context": "https://schema.org",
          "@type": "Product",
          name: product.product_name,
          url: pageUrl,
          image: (product.images || []).map((i) => i.image_url).filter(Boolean),
          description: product.short_description || product.full_description || product.product_name,
          sku: product.sku,
          brand: { "@type": "Brand", name: "AAYNA" },
          category: product.category_name,
          offers: {
            "@type": "Offer",
            url: pageUrl,
            price: String(effectivePrice(product) ?? product.selling_price ?? 0),
            priceCurrency: "BDT",
            availability: isOutOfStock(product) ? "https://schema.org/OutOfStock" : "https://schema.org/InStock",
          },
        }
      : null
  );

  const siteOrigin = typeof window !== "undefined" ? window.location.origin : "";
  useJsonLd(
    "breadcrumb",
    product
      ? {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: siteOrigin + "/" },
            { "@type": "ListItem", position: 2, name: "The Edit", item: siteOrigin + "/shop" },
            { "@type": "ListItem", position: 3, name: product.category_name || "Category", item: siteOrigin + "/category/" + product.category_slug },
            { "@type": "ListItem", position: 4, name: product.product_name, item: pageUrl },
          ],
        }
      : null
  );

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-12 gap-10 animate-pulse">
          <div className="md:col-span-7 aspect-[4/5] bg-aayna-mist" />
          <div className="md:col-span-5 space-y-4">
            <div className="h-8 w-3/4 bg-aayna-mist" />
            <div className="h-6 w-1/3 bg-aayna-mist" />
            <div className="h-24 bg-aayna-mist" />
          </div>
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <p className="text-aayna-charcoal text-lg mb-2">Product not found.</p>
        <p className="text-aayna-taupe text-sm mb-6">This piece may have been removed or the link is incorrect.</p>
        <Link to="/shop" className="text-aayna-burgundy underline underline-offset-2 text-sm">Browse The Edit</Link>
      </div>
    );
  }

  if (!product) return null;

  const oos = isOutOfStock(product);
  const discount = discountPercent(product);
  const price = effectivePrice(product);
  const image = product.images?.[0];
  const related = (data?.related || []).filter((p) => p.id !== product.id).slice(0, 4);

  const handleAddToCart = () => {
    if (oos) return;
    addItem(product, qty);
    toast.success(`${product.product_name} added to cart`);
  };
  const buyNow = () => {
    if (oos) return;
    addItem(product, qty);
    navigate("/cart");
  };

  const waNumber = settings?.whatsapp_number;
  const waAvailable = waNumber && !isPlaceholder(waNumber);
  const waDigits = (waNumber || "").replace(/[^0-9]/g, "");
  const waLink = waAvailable
    ? `https://wa.me/${waDigits}?text=${encodeURIComponent(`Hi AAYNA, I'm interested in "${product.product_name}" (${product.sku}).`)}`
    : null;

  const detailRows = [
    ["Material", product.material],
    ["Color", product.color],
    ["Size", product.size],
    ["Weight", product.weight],
    ["SKU", product.sku],
  ].filter(([, v]) => v);

  return (
    <div className="bg-aayna-cream pb-24 md:pb-0">
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5">
        <nav className="flex items-center gap-1.5 text-xs text-aayna-taupe flex-wrap">
          <Link to="/shop" className="hover:text-aayna-burgundy">The Edit</Link>
          <ChevronRight className="h-3 w-3" />
          <Link to={`/category/${product.category_slug}`} className="hover:text-aayna-burgundy">{product.category_name}</Link>
          <ChevronRight className="h-3 w-3" />
          <span className="text-aayna-charcoal line-clamp-1">The Object</span>
        </nav>
      </section>

      {/* ================= THE OBJECT — first viewport ================= */}
      <section className="relative py-5 md:py-8">
        <div
          aria-hidden="true"
          className="hidden md:block absolute rounded-full border border-aayna-burgundy/[0.08] w-[420px] h-[420px] right-[-10%] top-[-4%]"
        />
        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-x-8">
          <div className="md:col-span-7 relative z-10">
            <div className="relative aspect-[4/5] bg-aayna-mist overflow-hidden">
              <ProductImage
                testId="product-main-image"
                src={image?.image_url}
                alt={image?.alt_text || product.product_name}
                className="absolute inset-0"
                iconClassName="h-10 w-10"
                eager
              />
              {oos && (
                <span className="absolute left-3 bottom-3 text-[11px] uppercase tracking-wider text-aayna-taupe bg-aayna-cream/90 px-2.5 py-1.5">
                  Currently unavailable
                </span>
              )}
            </div>
            {/* Detail view — a second, wider real image if one exists; a CSS
                crop of the same photo otherwise (never presented as a second
                photograph if only one is real). */}
            {product.images?.length > 1 ? (
              <div className="mt-5 relative aspect-video bg-aayna-mist overflow-hidden">
                <ProductImage
                  src={product.images[1].image_url}
                  alt={product.images[1].alt_text || product.product_name}
                  className="absolute inset-0"
                  iconClassName="h-8 w-8"
                />
              </div>
            ) : image?.image_url ? (
              <div className="mt-5 relative aspect-video bg-aayna-mist overflow-hidden">
                <img
                  src={image.image_url}
                  alt=""
                  aria-hidden="true"
                  className="w-full h-full object-cover"
                  style={{ objectPosition: "32% 42%", transform: "scale(1.9)" }}
                />
                <span className="absolute left-3 bottom-3 text-[10px] uppercase tracking-wider text-white bg-aayna-burgundy-dark/50 px-2.5 py-1">
                  Detail, actual finish
                </span>
              </div>
            ) : null}
          </div>

          <div className="md:col-span-5 flex flex-col justify-center relative z-10">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-2.5">The Object</p>
            <h1 className="font-display font-semibold text-3xl md:text-[42px] leading-tight text-aayna-charcoal">
              {product.product_name}
            </h1>
            <div className="flex items-baseline gap-2.5 mt-3">
              <span data-testid="product-price" className="font-display font-semibold text-2xl text-aayna-burgundy">
                {formatBDT(price)}
              </span>
              {discount > 0 && (
                <>
                  <span className="text-aayna-taupe line-through text-base">{formatBDT(product.selling_price)}</span>
                  <span className="text-aayna-coral-dark text-xs font-bold">-{discount}%</span>
                </>
              )}
            </div>
            {product.short_description && (
              <p className="text-aayna-taupe text-sm leading-relaxed mt-4 max-w-md">{product.short_description}</p>
            )}

            {!oos && (
              <div className="flex items-center border border-aayna-beige w-fit mt-6">
                <button
                  data-testid="qty-decrease"
                  onClick={() => setQty((q) => Math.max(1, q - 1))}
                  aria-label="Decrease quantity"
                  className="h-11 w-11 flex items-center justify-center hover:bg-aayna-mist"
                >
                  <Minus className="h-4 w-4" />
                </button>
                <span data-testid="qty-value" className="w-10 text-center font-semibold text-sm">{qty}</span>
                <button
                  data-testid="qty-increase"
                  onClick={() => setQty((q) => Math.min(product.stock_quantity, q + 1))}
                  aria-label="Increase quantity"
                  className="h-11 w-11 flex items-center justify-center hover:bg-aayna-mist"
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="hidden md:flex gap-3 mt-4">
              <button
                data-testid="add-to-cart-button"
                onClick={handleAddToCart}
                disabled={oos}
                className="bg-aayna-coral text-white font-semibold text-sm px-8 h-12 hover:bg-aayna-coral-dark transition-colors disabled:bg-aayna-taupe disabled:cursor-not-allowed"
              >
                {oos ? "Out of Stock" : "Add to Cart"}
              </button>
              <button
                onClick={buyNow}
                disabled={oos}
                className="border border-aayna-burgundy text-aayna-burgundy font-semibold text-sm px-7 h-12 hover:bg-aayna-mist transition-colors disabled:border-aayna-beige disabled:text-aayna-taupe disabled:cursor-not-allowed"
              >
                Buy Now
              </button>
            </div>
            {oos && (
              <p className="text-aayna-taupe text-sm mt-3">
                This piece is currently unavailable — check back soon, or explore the rest of the edit.
              </p>
            )}

            {waAvailable && (
              <a
                data-testid="whatsapp-inquiry"
                href={waLink}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 mt-4 text-sm text-aayna-taupe border-b border-aayna-beige w-fit hover:text-aayna-burgundy hover:border-aayna-burgundy transition-colors"
              >
                Have a question? Inquire on WhatsApp
              </a>
            )}

            <div className="mt-6 pt-5 border-t border-aayna-beige flex flex-col gap-2.5 text-[13px] text-aayna-taupe">
              <Link to="/delivery-policy" className="underline underline-offset-2 hover:text-aayna-burgundy w-fit">
                Delivered nationwide. Cash on Delivery available — see delivery policy
              </Link>
              <Link to="/returns" className="underline underline-offset-2 hover:text-aayna-burgundy w-fit">
                See our Returns &amp; Exchange policy
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ================= DESCRIPTION ================= */}
      {product.full_description && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-14">
          <div className="md:max-w-2xl">
            <h2 className="font-display font-semibold text-xl text-aayna-burgundy-dark mb-2.5">Description</h2>
            <p className="text-aayna-taupe text-sm leading-[1.85] max-w-prose">{product.full_description}</p>
          </div>
        </section>
      )}

      {/* ================= THE DETAILS ================= */}
      {detailRows.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-9 md:py-14 border-t border-aayna-beige">
          <div className="md:max-w-md">
            <p className="text-aayna-coral-dark text-xs font-bold tracking-[0.22em] uppercase mb-5">The Details</p>
            <dl>
              {detailRows.map(([k, v]) => (
                <div key={k} className="flex justify-between py-3 border-b border-aayna-beige text-sm">
                  <dt className="text-aayna-taupe">{k}</dt>
                  <dd className="text-aayna-charcoal font-semibold">{v}</dd>
                </div>
              ))}
              <div className="flex justify-between py-3 text-sm">
                <dt className="text-aayna-taupe">Availability</dt>
                <dd className={`font-semibold ${oos ? "text-red-700" : "text-green-700"}`}>
                  {oos ? "Out of stock" : `${product.stock_quantity} in stock`}
                </dd>
              </div>
            </dl>
          </div>
        </section>
      )}

      {/* ================= CONTINUE THE EDIT ================= */}
      {related.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-16">
          <div className="flex items-baseline justify-between mb-6">
            <h2 className="font-display font-semibold text-xl md:text-2xl text-aayna-burgundy-dark">Continue the Edit</h2>
            <Link to={`/category/${product.category_slug}`} className="text-xs text-aayna-taupe underline underline-offset-2 hover:text-aayna-burgundy">
              View all {product.category_name} →
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
            {related.map((p) => (
              <ProductCard key={p.id} product={p} variant="editorial" />
            ))}
          </div>
        </section>
      )}

      {/* ================= STICKY MOBILE ADD TO CART ================= */}
      <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white border-t border-aayna-beige p-3 flex items-center gap-3">
        <div className="flex-shrink-0">
          <p className="text-xs text-aayna-taupe">Price</p>
          <p className="font-display font-semibold text-aayna-burgundy text-lg leading-none">{formatBDT(price)}</p>
        </div>
        <button
          data-testid="add-to-cart-button-mobile"
          onClick={handleAddToCart}
          disabled={oos}
          className="flex-1 h-12 bg-aayna-coral text-white font-semibold disabled:bg-aayna-taupe disabled:cursor-not-allowed"
        >
          {oos ? "Out of Stock" : "Add to Cart"}
        </button>
      </div>
    </div>
  );
}
