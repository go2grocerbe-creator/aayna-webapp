import { useParams, useNavigate } from "react-router-dom";
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

  const { data: category } = useQuery({
    queryKey: ["category", slug],
    queryFn: () => getCategory(slug),
  });

  useSeo({
    title: category?.name || "Category",
    description: category?.description
      ? `${category.description} Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`
      : `Shop ${category?.name || "accessories"} — women's accessories in Bangladesh from AAYNA.`,
    image: category?.image_url,
  });

  const handleCategoryChange = (nextSlug) => {
    navigate(nextSlug ? `/category/${nextSlug}` : "/shop");
  };

  return (
    <TheEdit
      categories={categories}
      activeCategory={slug}
      onCategoryChange={handleCategoryChange}
      contextLabel={category?.name ? `The Edit — ${category.name}` : undefined}
    />
  );
}
