import { apiClient } from "./apiClient";

export async function listarAlertas({ eventoId, nivel, estado } = {}) {
  const { data } = await apiClient.get("/alertas", {
    params: { evento_id: eventoId, nivel, estado },
  });
  return data;
}

export async function actualizarAlerta(id, estado) {
  const { data } = await apiClient.put(`/alertas/${id}`, { estado });
  return data;
}
