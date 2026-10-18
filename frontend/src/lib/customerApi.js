import axios from "axios";
import { API } from "@/lib/api";

// Customer sessions live in an HttpOnly cookie set by the API - this code never
// sees or stores a session token. Every state-changing request carries the
// X-AAYNA-CSRF header, which the backend requires (cross-site forms cannot add it).
const client = axios.create({ baseURL: API, timeout: 15000, withCredentials: true });
client.interceptors.request.use((cfg) => {
  if ((cfg.method || "get").toLowerCase() !== "get") {
    cfg.headers = { ...(cfg.headers || {}), "X-AAYNA-CSRF": "1" };
  }
  return cfg;
});

const data = (p) => p.then((r) => r.data);

/** Turns any API error into { message, fields, code } for forms. */
export function apiError(err, fallback = "Something went wrong. Please try again.") {
  const d = err?.response?.data?.detail;
  if (!err?.response) return { message: "We couldn't reach AAYNA. Check your connection and try again.", fields: {} };
  if (typeof d === "string") return { message: d, fields: {}, status: err.response.status };
  if (d && typeof d === "object") return { message: d.message || fallback, fields: d.fields || {}, code: d.code, status: err.response.status };
  return { message: fallback, fields: {}, status: err.response.status };
}

export const customerConfig = () => data(client.get("/customer/config"));
export const getSession = () => data(client.get("/customer/session"));
export const register = (body) => data(client.post("/customer/register", body));
export const login = (body) => data(client.post("/customer/login", body));
export const logout = () => data(client.post("/customer/logout"));
export const verifyEmail = (token) => data(client.post("/customer/verify-email", { token }));
export const resendVerification = (email) => data(client.post("/customer/resend-verification", { email }));
export const forgotPassword = (email) => data(client.post("/customer/forgot-password", { email }));
export const resetPassword = (body) => data(client.post("/customer/reset-password", body));
export const confirmEmailChange = (token) => data(client.post("/customer/confirm-email-change", { token }));

export const getMe = () => data(client.get("/account/me"));
export const updateProfile = (body) => data(client.patch("/account/profile", body));
export const getSecurity = () => data(client.get("/account/security"));
export const changePassword = (body) => data(client.post("/account/password", body));
export const requestEmailChange = (body) => data(client.post("/account/email", body));
export const revokeOtherSessions = () => data(client.post("/account/sessions/revoke-others"));
export const revokeSession = (id) => data(client.delete(`/account/sessions/${id}`));
export const logoutAll = () => data(client.post("/account/logout-all"));
export const confirmGoogleLink = () => data(client.post("/account/link/google/confirm"));
export const unlinkGoogle = () => data(client.delete("/account/link/google"));
export const requestDeletion = () => data(client.post("/account/delete-request", { confirm: "DELETE" }));

export const listAddresses = () => data(client.get("/account/addresses"));
export const addAddress = (body) => data(client.post("/account/addresses", body));
export const updateAddress = (id, body) => data(client.put(`/account/addresses/${id}`, body));
export const deleteAddress = (id) => data(client.delete(`/account/addresses/${id}`));

export const listOrders = () => data(client.get("/account/orders"));
export const getAccountOrder = (num) => data(client.get(`/account/orders/${encodeURIComponent(num)}`));
export const claimOrder = (order_number, confirmation_token) =>
  data(client.post("/account/orders/claim", { order_number, confirmation_token }));
export const claimOrderByEmail = (order_number) => data(client.post("/account/orders/claim-by-email", { order_number }));
export const confirmOrderClaim = (token) => data(client.post("/account/orders/confirm-claim", { token }));
export const getRewards = () => data(client.get("/account/rewards"));
export const getWelcomeOffer = () => data(client.get("/promotions/welcome"));

// Cart validation and checkout go through this client too so the session
// cookie (if any) links the order to the signed-in account server-side.
export const validateCartWithSession = (body) => data(client.post("/cart/validate", body));
export const checkoutWithSession = (body) => data(client.post("/checkout", body));

export const googleStartUrl = (next = "/account", mode = "login") =>
  `${API}/auth/google/start?${new URLSearchParams({ next, mode }).toString()}`;

/** Reads #token=... from the URL fragment, then removes it from the address bar. */
export function takeFragmentToken() {
  if (typeof window === "undefined") return null;
  const m = window.location.hash.match(/token=([A-Za-z0-9_-]+)/);
  if (m) window.history.replaceState(null, "", window.location.pathname + window.location.search);
  return m ? m[1] : null;
}
