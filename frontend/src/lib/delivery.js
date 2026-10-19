// AAYNA delivery policy (founder decision 2026-10-19). The server decides the
// charge at checkout (backend/delivery.py); this mirrors it only for display
// before the server answers. Policy values come from /api/settings
// (`delivery_policy`) or a /api/cart/validate answer.
export const DEFAULT_DELIVERY_POLICY = { charge: 100, free_threshold: 1500 };

export function deliveryPolicy(source) {
  const p = source?.delivery_policy || source || {};
  const n = (v, d) => (Number.isFinite(Number(v)) && v !== null && v !== "" ? Number(v) : d);
  return {
    charge: n(p.charge, DEFAULT_DELIVERY_POLICY.charge),
    free_threshold: n(p.free_threshold, DEFAULT_DELIVERY_POLICY.free_threshold),
  };
}

// `merchandiseSubtotal` is BEFORE promotional discounts.
export function deliveryFor(merchandiseSubtotal, policy = DEFAULT_DELIVERY_POLICY) {
  const sub = Math.max(0, Number(merchandiseSubtotal) || 0);
  if (sub <= 0) return { charge: 0, free: false, remaining: policy.free_threshold, progress: 0 };
  const free = policy.free_threshold > 0 && sub >= policy.free_threshold;
  const remaining = free || policy.free_threshold <= 0 ? 0 : policy.free_threshold - sub;
  const progress = policy.free_threshold > 0 ? Math.min(1, sub / policy.free_threshold) : 0;
  return { charge: free ? 0 : policy.charge, free, remaining, progress };
}
