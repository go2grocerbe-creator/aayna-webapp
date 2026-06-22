import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;
const TOKEN_KEY = "aayna_admin_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const api = axios.create({ baseURL: API });
api.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export const fullImageUrl = (urlPath) => `${BACKEND}${urlPath}`;

// Auth
export const adminLogin = (email, password) =>
  axios.post(`${API}/admin/login`, { email, password }).then((r) => r.data);
export const adminMe = () => api.get("/admin/me").then((r) => r.data);

// Dashboard
export const getDashboard = () => api.get("/admin/dashboard").then((r) => r.data);

// Products
export const getAdminProducts = (params) => api.get("/admin/products", { params }).then((r) => r.data);
export const getAdminProduct = (id) => api.get(`/admin/products/${id}`).then((r) => r.data);
export const createProduct = (d) => api.post("/admin/products", d).then((r) => r.data);
export const updateProduct = (id, d) => api.put(`/admin/products/${id}`, d).then((r) => r.data);
export const deleteProduct = (id) => api.delete(`/admin/products/${id}`).then((r) => r.data);

// Categories
export const getAdminCategories = () => api.get("/admin/categories").then((r) => r.data);
export const createCategory = (d) => api.post("/admin/categories", d).then((r) => r.data);
export const updateCategory = (id, d) => api.put(`/admin/categories/${id}`, d).then((r) => r.data);

// Orders
export const getAdminOrders = (params) => api.get("/admin/orders", { params }).then((r) => r.data);
export const getAdminOrder = (num) => api.get(`/admin/orders/${num}`).then((r) => r.data);
export const updateOrder = (num, d) => api.put(`/admin/orders/${num}`, d).then((r) => r.data);

// Inventory
export const getInventory = (lowOnly) =>
  api.get("/admin/inventory", { params: lowOnly ? { low_only: true } : {} }).then((r) => r.data);
export const adjustStock = (id, d) => api.post(`/admin/inventory/${id}/adjust`, d).then((r) => r.data);
export const getInventoryLogs = (id) => api.get(`/admin/inventory/${id}/logs`).then((r) => r.data);

// Customers
export const getCustomers = (params) => api.get("/admin/customers", { params }).then((r) => r.data);
export const getCustomer = (id) => api.get(`/admin/customers/${id}`).then((r) => r.data);

// Settings
export const getAdminSettings = () => api.get("/admin/settings").then((r) => r.data);
export const updateAdminSettings = (d) => api.put("/admin/settings", d).then((r) => r.data);

// Upload
export const uploadImage = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/admin/upload", fd).then((r) => r.data);
};

// Import / Export
export const importProducts = (file) => {
  const fd = new FormData();
  fd.append("file", file);
  return api.post("/admin/import/products", fd).then((r) => r.data);
};
export const downloadCsv = async (kind, filename) => {
  const res = await api.get(`/admin/export/${kind}`, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};

export default api;
