// src/hooks/useWPAuth.js
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function useWPAuth() {
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");

    if (token) {
      localStorage.setItem("wp_jwt", token);

      // 🔐 clean URL (security + UX)
      window.history.replaceState({}, document.title, "/");
    }

    const storedToken = localStorage.getItem("wp_jwt");
    if (!storedToken) {
      alert("Authentication required");
      window.location.href = "https://retano360.com";
    }
  }, [navigate]);
}
