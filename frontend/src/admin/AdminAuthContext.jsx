import { createContext, useContext, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { adminMe, adminLogin, adminLogout, getToken, setToken, clearToken } from "@/admin/adminApi";

const AdminAuthContext = createContext(null);

export function AdminAuthLayout() {
  const [user, setUser] = useState(null); // null = checking, false = unauth, object = authed

  useEffect(() => {
    if (!getToken()) {
      setUser(false);
      return;
    }
    adminMe()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(false);
      });
  }, []);

  const login = async (email, password) => {
    const data = await adminLogin(email, password);
    setToken(data.token);
    setUser(data.user);
    return data;
  };

  const logout = async () => {
    try {
      if (getToken()) await adminLogout();
    } catch {
      // token already invalid/expired: nothing to revoke server-side
    }
    clearToken();
    setUser(false);
  };

  // UI convenience only - the API enforces every permission server-side.
  const can = (perm) => Boolean(user && Array.isArray(user.permissions) && user.permissions.includes(perm));

  return (
    <AdminAuthContext.Provider value={{ user, login, logout, can }}>
      <Outlet />
    </AdminAuthContext.Provider>
  );
}

export const useAdminAuth = () => useContext(AdminAuthContext);
