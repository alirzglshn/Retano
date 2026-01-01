import axios from "axios";

const api = axios.create({
  baseURL: "https://panel.retano360.com",
});


api.interceptors.request.use((config) => {
  const token = localStorage.getItem("wp_jwt");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
