import { useEffect } from "react";
import AppRouter from "./router/AppRouter";
import { useAuthStore } from "./store/authStore";

export default function App() {
  useEffect(() => {
    const handleAuthExpired = () => {
      useAuthStore.getState().clearSession(true);
    };

    window.addEventListener("biat-auth-expired", handleAuthExpired);
    void useAuthStore.getState().bootstrap();

    return () => {
      window.removeEventListener("biat-auth-expired", handleAuthExpired);
    };
  }, []);

  return <AppRouter />;
}
