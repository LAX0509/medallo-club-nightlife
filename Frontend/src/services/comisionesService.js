import { apiClient } from "./apiClient";

export async function listarComisiones({ promotorId, eventoId, estado } = {}) {
  const { data } = await apiClient.get("/comisiones", {
    params: { promotor_id: promotorId, evento_id: eventoId, estado },
  });
  return data;
}

export async function crearComision(payload) {
  const { data } = await apiClient.post("/comisiones", payload);
  return data;
}

export async function actualizarComision(id, payload) {
  const { data } = await apiClient.put(`/comisiones/${id}`, payload);
  return data;
}
