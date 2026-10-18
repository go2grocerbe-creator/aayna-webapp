import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getSession, logout as apiLogout, customerConfig } from "@/lib/customerApi";

const Ctx = createContext(null);

export function CustomerAuthProvider({ children }) {
  const [state, setState] = useState({ loading: true, account: null });
  const [config, setConfig] = useState({ google_enabled: false, password_min_length: 12 });

  const refresh = useCallback(async () => {
    try {
      const s = await getSession();
      setState({ loading: false, account: s.authenticated ? s.account : null });
      return s.authenticated ? s.account : null;
    } catch {
      setState({ loading: false, account: null });
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
    customerConfig().then(setConfig).catch(() => {});
  }, [refresh]);

  const setAccount = useCallback((account) => setState({ loading: false, account }), []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      setState({ loading: false, account: null });
    }
  }, []);

  const value = useMemo(
    () => ({ ...state, config, refresh, setAccount, logout, signedIn: !!state.account }),
    [state, config, refresh, setAccount, logout]
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useCustomer() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useCustomer must be used inside CustomerAuthProvider");
  return v;
}
