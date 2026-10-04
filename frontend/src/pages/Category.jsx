import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCategory } from "@/lib/api";
import { useCategories } from "@/hooks/useStore";
import TheEdit from "@/components/TheEdit";
import { useSeo } from "@/lib/seo";

// /category/:slug — same D2 "The Edit" presentation as /shop, just with the
// current category already active. Switching to a different category in the
// nav navigates to that category's own route (real per-category SEO/URL,
// not client-side-only filtering), preserving existing route architecture.
const EDIT_CATEGORY_SLUGS = ["earrings", "necklaces", "rings"];

export default function Category() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { data: allCategories = [] } = useCategories();
  const categories = allCategories.filter((c) => EDIT_CATEGORY_SLUGS.includes(c.slug));

  const { data: category, isLoading, isError } = useQuery({
    queryKey: ["category", slug],
    queryFn: () => getCategory(slug),
    retry: 1,
  });
  // L4: an unknown slug used to fall through to a generic "Category" page,
  // fully indexable, with no products and no explanation - a fake empty SEO
  // page. A real but not-yet-launched category (Bracelets, Hair Accessories,
  // Gift Sets) still renders normally, just noindex - it's not "not found",
  // it just has no launch inventory to rank on yet.
  const notFound = !isLoading && (isError || !category);
  const isLaunchCategory = !!category && EDIT_CATEGORY_SLUGS.includes(category.slug);

  useSeo({
    title: category?.name || (notFound ? "Category Not Found" : "Category"),
    description: category?.description
      ? `${category.description} Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`
      : `Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`,
    image: category?.image_url,
    noindex: notFound ? true : !isLaunchCategory,
  });

  const handleCategoryChange = (nextSlug) => {
    navigate(nextSlug ? `/category/${nextSlug}` : "/shop");
  };

  if (notFound) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <p className="text-aayna-charcoal text-lg mb-2">Category not found.</p>
        <p className="text-aayna-taupe text-sm mb-6">This category may have been renamed or the link is incorrect.</p>
        <Link to="/shop" className="text-aayna-burgundy underline underline-offset-2 text-sm">Browse The Edit</Link>
      </div>
    );
  }

  return (
    <TheEdit
      categories={categories}
      activeCategory={slug}
      onCategoryChange={handleCategoryChange}
      contextLabel={category?.name ? `The Edit — ${category.name}` : undefined}
    />
  );
}
