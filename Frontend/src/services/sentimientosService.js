import { apiClient } from "./apiClient";

export async function obtenerPanelSentimientos(dias = 14) {
  const { data } = await apiClient.get("/sentimientos/panel", { params: { dias } });
  return data;
}

export async function listarConversaciones({ estado = "todas", canal, limite = 50 } = {}) {
  const params = { estado, limite };
  if (canal) params.canal = canal;
  const { data } = await apiClient.get("/sentimientos/conversaciones", { params });
  return data;
}

export async function obtenerConversacion(id) {
  const { data } = await apiClient.get(`/sentimientos/conversaciones/${encodeURIComponent(id)}`);
  return data;
}

export async function resolverConversacion(id) {
  const { data } = await apiClient.post(`/sentimientos/conversaciones/${encodeURIComponent(id)}/resolver`);
  return data;
}

export async function analizarTexto(texto, usarIa = false) {
  const { data } = await apiClient.post("/sentimientos/analizar", { texto, usar_ia: usarIa });
  return data;
}
