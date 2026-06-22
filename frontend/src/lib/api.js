import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const client = axios.create({ baseURL: API });

export const getSettings = () => client.get("/settings").then((r) => r.data);
export const getCategories = () => client.get("/categories").then((r) => r.data);
export const getCategory = (slug) => client.get(`/categories/${slug}`).then((r) => r.data);
export const getProducts = (params) => client.get("/products", { params }).then((r) => r.data);
export const getProduct = (slug) => client.get(`/products/${slug}`).then((r) => r.data);
export const getDistricts = () => client.get("/districts").then((r) => r.data);
export const validateCart = (payload) => client.post("/cart/validate", payload).then((r) => r.data);
export const checkout = (payload) => client.post("/checkout", payload).then((r) => r.data);
export const getOrder = (orderNumber) => client.get(`/orders/${orderNumber}`).then((r) => r.data);
export const trackOrder = (payload) => client.post("/track", payload).then((r) => r.data);

export default client;
