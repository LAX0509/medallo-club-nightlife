import { apiClient } from "./apiClient";

export async function listarUsuarios({ page = 1, limit = 20, rol } = {}) {
  const { data } = await apiClient.get("/usuarios", { params: { page, limit, rol } });
  return data;
}

export async function crearUsuario(payload) {
  const { data } = await apiClient.post("/usuarios", payload);
  return data;
}

export async function actualizarUsuario(id, payload) {
  const { data } = await apiClient.put(`/usuarios/${id}`, payload);
  return data;
}
