import axios from "axios";

// Usa el mismo nombre de host que cargó la página. Así, en el celular las
// peticiones van al PC por la red Wi-Fi en vez de buscar localhost en el celular.
const protocoloApi = window.location.protocol === "https:" ? "https:" : "http:";
const hostApi = window.location.hostname || "localhost";
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? `${protocoloApi}//${hostApi}:8000/api/v1`;

export const apiClient = axios.create({ baseURL: BASE_URL });

const TOKEN_STORAGE_KEY = "nightlife_ds_token";

export function guardarToken(token) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function obtenerToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function limpiarToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

apiClient.interceptors.request.use((config) => {
  const token = obtenerToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      limpiarToken();
      if (!window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  }
);

export function mensajeDeError(error, fallback = "Ocurrió un error inesperado") {
  const detalle = error?.response?.data?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) {
    return detalle.map((d) => d.msg ?? JSON.stringify(d)).join(" · ");
  }
  return fallback;
}
