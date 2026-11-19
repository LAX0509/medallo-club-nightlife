import { apiClient } from "./apiClient";

export async function listarInvitados({ eventoId, promotorId, page = 1, limit = 50 } = {}) {
  const { data } = await apiClient.get("/invitados", {
    params: { evento_id: eventoId, promotor_id: promotorId, page, limit },
  });
  return data;
}

export async function obtenerResumenInvitados({ eventoId, promotorId } = {}) {
  const { data } = await apiClient.get("/invitados/resumen", {
    params: { evento_id: eventoId, promotor_id: promotorId },
  });
  return data;
}

export async function registrarInvitado(payload) {
  const { data } = await apiClient.post("/invitados", payload);
  return data;
}

export async function eliminarInvitado(id) {
  await apiClient.delete(`/invitados/${id}`);
}
