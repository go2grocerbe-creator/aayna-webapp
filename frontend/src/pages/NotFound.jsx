import { Link } from "react-router-dom";
import { Compass } from "lucide-react";
import { useSeo } from "@/lib/seo";

export default function NotFound() {
  useSeo({ title: "Page Not Found", description: "The page you're looking for doesn't exist.", noindex: true });
  return (
    <div data-testid="not-found-page" className="max-w-2xl mx-auto px-4 sm:px-6 py-20 md:py-28 text-center">
      <div className="h-16 w-16 rounded-full bg-aayna-mist flex items-center justify-center mx-auto mb-6">
        <Compass className="h-8 w-8 text-aayna-rose" />
      </div>
      <p className="text-aayna-rose font-medium text-sm tracking-wide uppercase mb-2">404</p>
      <h1 className="font-display text-4xl md:text-5xl font-bold text-aayna-charcoal">Page not found</h1>
      <p className="text-aayna-taupe mt-3 max-w-md mx-auto">
        The page you're looking for doesn't exist or may have moved. Let's get you back to shopping.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center mt-8">
        <Link
          to="/"
          data-testid="notfound-home-link"
          className="h-12 px-8 bg-aayna-rose text-white font-semibold inline-flex items-center justify-center hover:bg-aayna-rose-dark transition-colors"
        >
          Back to Home
        </Link>
        <Link
          to="/shop"
          data-testid="notfound-shop-link"
          className="h-12 px-8 border border-aayna-rose text-aayna-rose font-semibold inline-flex items-center justify-center hover:bg-aayna-mist transition-colors"
        >
          Continue Shopping
        </Link>
      </div>
    </div>
  );
}
