import { apiClient } from "./apiClient";

export async function obtenerResumenEvento(eventoId) {
  const { data } = await apiClient.get(`/dashboard/eventos/${eventoId}/resumen`);
  return data;
}

export async function generarInformeJornada(eventoId, usarIa = true) {
  const { data } = await apiClient.post(`/dashboard/eventos/${eventoId}/informe`, { usar_ia: usarIa });
  return data;
}
