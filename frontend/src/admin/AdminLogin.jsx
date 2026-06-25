import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useAdminAuth } from "@/admin/AdminAuthContext";

export default function AdminLogin() {
  const { user, login } = useAdminAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) navigate("/admin", { replace: true });
  }, [user, navigate]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email.trim(), password);
      toast.success("Welcome back");
      navigate("/admin", { replace: true });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      const message = typeof detail === "string" ? detail : "Invalid email or password";
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-aayna-cream flex items-center justify-center px-4 font-body">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <span className="font-display text-4xl font-extrabold text-aayna-charcoal tracking-tight">AAYNA</span>
          <p className="text-gray-500 mt-1">Admin Dashboard</p>
        </div>
        <form onSubmit={submit} className="bg-white border border-gray-200 rounded-lg p-7 shadow-sm">
          <h1 className="text-xl font-bold text-aayna-charcoal mb-5">Sign in</h1>
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
          <input
            data-testid="admin-login-email"
            type="email"
            value={email}
            onChange={(e) => { setEmail(e.target.value); setError(""); }}
            placeholder="admin@aayna.xyz"
            className="w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose focus:ring-1 focus:ring-aayna-rose mb-4"
            required
          />
          <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
          <input
            data-testid="admin-login-password"
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(""); }}
            placeholder="••••••••"
            className="w-full h-11 border border-gray-300 rounded-md px-3 outline-none focus:border-aayna-rose focus:ring-1 focus:ring-aayna-rose mb-4"
            required
          />
          {error && (
            <p data-testid="admin-login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2 mb-4">
              {error}
            </p>
          )}
          <button
            data-testid="admin-login-submit"
            type="submit"
            disabled={busy}
            className="w-full h-11 bg-aayna-rose text-white font-semibold rounded-md hover:bg-aayna-rose-dark transition-colors disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}
            Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
