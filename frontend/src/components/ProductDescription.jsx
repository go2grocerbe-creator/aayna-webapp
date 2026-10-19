// Product description presentation, shared by the product page and the admin preview.
// Content is plain text (validated on the server) rendered as text, never as HTML.
// Sections appear only when there is verified content for them.
import { ChevronDown } from "lucide-react";

export const paragraphs = (text) =>
  String(text || "")
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

function Fold({ title, children, open, testid }) {
  return (
    <details open={open} data-testid={testid} className="group border-b border-aayna-beige">
      <summary className="flex items-center justify-between gap-4 cursor-pointer list-none min-h-[52px] py-3 [&::-webkit-details-marker]:hidden">
        <span className="font-display font-semibold text-lg text-aayna-burgundy-dark">{title}</span>
        <ChevronDown className="h-4 w-4 text-aayna-taupe transition-transform group-open:rotate-180" aria-hidden="true" />
      </summary>
      <div className="pb-6">{children}</div>
    </details>
  );
}

export default function ProductDescription({ product, availability }) {
  const paras = paragraphs(product.full_description);
  const highlights = (product.highlights || []).filter(Boolean);
  const rows = [
    ["Material", product.material],
    ["Color", product.color],
    ["Size", product.size],
    ["Weight", product.weight],
    ["SKU", product.sku],
  ].filter(([, v]) => v);
  const hasDetails = highlights.length > 0 || rows.length > 0 || availability;
  if (!paras.length && !hasDetails && !product.care_note) return null;

  return (
    <div data-testid="product-description" className="md:max-w-2xl border-t border-aayna-beige">
      {paras.length > 0 && (
        <Fold title="Description" open testid="pd-description">
          <div className="space-y-4 text-aayna-charcoal/85 text-[15px] leading-[1.85] max-w-prose">
            {paras.map((p, i) => (
              <p key={i} className="whitespace-pre-line">{p}</p>
            ))}
          </div>
        </Fold>
      )}
      {hasDetails && (
        <Fold title="The details" open={!paras.length} testid="pd-details">
          {highlights.length > 0 && (
            <ul className="space-y-2 mb-5" data-testid="pd-highlights">
              {highlights.map((h, i) => (
                <li key={i} className="flex gap-3 text-[15px] text-aayna-charcoal/85 leading-relaxed">
                  <span className="mt-[0.7em] h-px w-3 flex-shrink-0 bg-aayna-burgundy" aria-hidden="true" />
                  <span>{h}</span>
                </li>
              ))}
            </ul>
          )}
          <dl>
            {rows.map(([k, v]) => (
              <div key={k} className="flex justify-between gap-6 py-3 border-b border-aayna-beige/70 text-sm last:border-b-0">
                <dt className="text-aayna-taupe">{k}</dt>
                <dd className="text-aayna-charcoal font-semibold text-right">{v}</dd>
              </div>
            ))}
            {availability && (
              <div className="flex justify-between gap-6 py-3 text-sm border-t border-aayna-beige/70">
                <dt className="text-aayna-taupe">Availability</dt>
                <dd className={`font-semibold ${availability.oos ? "text-red-700" : "text-green-700"}`}>{availability.label}</dd>
              </div>
            )}
          </dl>
        </Fold>
      )}
      {product.care_note && (
        <Fold title="Care" testid="pd-care">
          <p className="text-aayna-charcoal/85 text-[15px] leading-[1.85] whitespace-pre-line max-w-prose">{product.care_note}</p>
        </Fold>
      )}
    </div>
  );
}
