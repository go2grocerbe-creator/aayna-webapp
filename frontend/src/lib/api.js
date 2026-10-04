import axios from "axios";

// The storefront can render without a live API. In production the real API URL
// should be supplied through REACT_APP_BACKEND_URL. An empty value deliberately
// falls back to same-origin /api instead of producing "undefined/api".
const BACKEND_URL = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API = BACKEND_URL ? `${BACKEND_URL}/api` : "/api";

const client = axios.create({ baseURL: API, timeout: 10000 });

export const getSettings = () => client.get("/settings").then((r) => r.data);
export const getCategories = () => client.get("/categories").then((r) => r.data);
export const getCategory = (slug) => client.get(`/categories/${slug}`).then((r) => r.data);
export const getProducts = (params) => client.get("/products", { params }).then((r) => r.data);
export const getProduct = (slug) => client.get(`/products/${slug}`).then((r) => r.data);
export const getDistricts = () => client.get("/districts").then((r) => r.data);
export const validateCart = (payload) => client.post("/cart/validate", payload).then((r) => r.data);
export const checkout = (payload) => client.post("/checkout", payload).then((r) => r.data);
export const getOrder = (orderNumber, token) =>
  client.get(`/orders/${orderNumber}`, { params: { token } }).then((r) => r.data);
export const trackOrder = (payload) => client.post("/track", payload).then((r) => r.data);

export default client;
