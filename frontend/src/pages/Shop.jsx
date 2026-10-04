import { useSearchParams } from "react-router-dom";
import { useCategories } from "@/hooks/useStore";
import TheEdit from "@/components/TheEdit";
import { useSeo } from "@/lib/seo";

// The Edit — Shop (D2, concept-d2-the-edit.html). "All" is active when
// arriving directly at /shop; ?category=slug preselects a category, mirroring
// the previous Shop.jsx's own query-param pattern so old /shop?category=...
// links keep working.
const EDIT_CATEGORY_SLUGS = ["earrings", "necklaces", "rings"];

export default function Shop() {
  const [params, setParams] = useSearchParams();
  const { data: allCategories = [] } = useCategories();
  const categories = allCategories.filter((c) => EDIT_CATEGORY_SLUGS.includes(c.slug));

  const category = params.get("category") || null;
  const search = params.get("search") || "";

  useSeo({
    title: search ? `Search: ${search}` : "The Edit",
    description: "Browse the AAYNA edit — earrings, necklaces and rings, women's accessories in Bangladesh.",
  });

  const handleCategoryChange = (slug) => {
    const next = new URLSearchParams(params);
    if (slug) next.set("category", slug);
    else next.delete("category");
    setParams(next);
  };

  return (
    <TheEdit
      categories={categories}
      activeCategory={category}
      onCategoryChange={handleCategoryChange}
      search={search}
    />
  );
}
