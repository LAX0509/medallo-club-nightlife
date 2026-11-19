import { apiClient } from "./apiClient";

export async function login(email, password) {
  const { data } = await apiClient.post("/auth/login", { email, password });
  return data;
}

export async function registrarPromotor(datos) {
  const { data } = await apiClient.post("/auth/register", datos);
  return data;
}

export async function obtenerUsuarioActual() {
  const { data } = await apiClient.get("/usuarios/me");
  return data;
}
