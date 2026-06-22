import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { getProducts } from "@/lib/api";
import { useSettings, useCategories } from "@/hooks/useStore";
import ProductGrid from "@/components/ProductGrid";
import TrustBadges from "@/components/TrustBadges";

function SectionHeading({ title, subtitle, link, linkLabel }) {
  return (
    <div className="flex items-end justify-between mb-7 md:mb-9">
      <div>
        <h2 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">{title}</h2>
        {subtitle && <p className="text-aayna-taupe mt-2 text-sm md:text-base max-w-xl">{subtitle}</p>}
      </div>
      {link && (
        <Link to={link} className="hidden sm:flex items-center gap-1.5 text-sm font-medium text-aayna-rose hover:gap-2.5 transition-all whitespace-nowrap">
          {linkLabel} <ArrowRight className="h-4 w-4" />
        </Link>
      )}
    </div>
  );
}

export default function Home() {
  const { data: settings } = useSettings();
  const { data: categories = [] } = useCategories();
  const { data: newArrivals = [], isLoading: loadingNew } = useQuery({
    queryKey: ["products", "new"],
    queryFn: () => getProducts({ new_arrival: true, limit: 8 }),
  });
  const { data: bestSellers = [], isLoading: loadingBest } = useQuery({
    queryKey: ["products", "best"],
    queryFn: () => getProducts({ best_seller: true, limit: 8 }),
  });

  return (
    <div>
      {/* Hero */}
      <section className="relative bg-aayna-mist overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid md:grid-cols-2 items-center gap-8 py-10 md:py-0">
          <div className="order-2 md:order-1 md:py-24 animate-fade-up">
            <p className="text-aayna-rose font-medium text-sm tracking-wide uppercase mb-3">{settings?.brand_name || "AAYNA"} · Bangladesh</p>
            <h1 className="font-display text-4xl sm:text-5xl lg:text-6xl font-bold text-aayna-charcoal leading-[1.08]">
              {settings?.hero_headline || "Everyday Accessories, Effortlessly Styled"}
            </h1>
            <p className="mt-5 text-base md:text-lg text-aayna-taupe max-w-md">
              {settings?.hero_subtitle || "Trendy, affordable, and feminine pieces selected for your everyday looks."}
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-8">
              <Link
                to="/shop"
                data-testid="hero-shop-now"
                className="h-12 px-8 bg-aayna-rose text-white font-semibold inline-flex items-center justify-center hover:bg-aayna-rose-dark transition-colors"
              >
                Shop Now
              </Link>
              <Link
                to="/category/earrings"
                className="h-12 px-8 border border-aayna-rose text-aayna-rose font-semibold inline-flex items-center justify-center hover:bg-white transition-colors"
              >
                Explore Earrings
              </Link>
            </div>
          </div>
          <div className="order-1 md:order-2 relative h-64 sm:h-80 md:h-[520px]">
            <img
              src={settings?.hero_image_url}
              alt="AAYNA accessories"
              className="absolute inset-0 w-full h-full object-cover"
            />
          </div>
        </div>
      </section>

      {/* Featured Categories */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
        <SectionHeading title="Shop by Category" subtitle="Find your everyday favourites." />
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 md:gap-6">
          {categories.map((c) => (
            <Link
              key={c.slug}
              to={`/category/${c.slug}`}
              data-testid={`home-category-${c.slug}`}
              className="group relative overflow-hidden aspect-[4/3] bg-aayna-mist"
            >
              <img src={c.image_url} alt={c.name} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute inset-0 bg-gradient-to-t from-aayna-charcoal/55 to-transparent" />
              <div className="absolute bottom-0 left-0 p-4 md:p-5">
                <h3 className="font-display text-xl md:text-2xl font-bold text-white">{c.name}</h3>
                <span className="text-white/85 text-xs md:text-sm">{c.product_count} items</span>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* New Arrivals */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-14 md:pb-20">
        <SectionHeading title="New Arrivals" subtitle="Fresh picks just added to the collection." link="/shop" linkLabel="View all" />
        <ProductGrid products={newArrivals.slice(0, 8)} loading={loadingNew} />
      </section>

      {/* Best Sellers */}
      <section className="bg-white border-y border-aayna-beige">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
          <SectionHeading title="Best Sellers" subtitle="Loved by our customers across Bangladesh." link="/shop" linkLabel="View all" />
          <ProductGrid products={bestSellers.slice(0, 8)} loading={loadingBest} />
        </div>
      </section>

      {/* Why shop with us */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-14 md:py-20">
        <div className="text-center mb-9">
          <h2 className="font-display text-3xl md:text-4xl font-bold text-aayna-charcoal">Why Shop With AAYNA</h2>
          <p className="text-aayna-taupe mt-2">Pretty pieces, fair prices, and a shopping experience you can trust.</p>
        </div>
        <TrustBadges />
      </section>
    </div>
  );
}
