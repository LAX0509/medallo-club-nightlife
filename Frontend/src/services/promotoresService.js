import { apiClient } from "./apiClient";

export async function obtenerMetaPromotor(eventoId) {
  const { data } = await apiClient.get("/promotores/me/meta", {
    params: { evento_id: eventoId },
  });
  return data;
}

export async function guardarMetaPromotor(eventoId, objetivo) {
  const { data } = await apiClient.put("/promotores/me/meta", {
    evento_id: eventoId,
    objetivo,
  });
  return data;
}
