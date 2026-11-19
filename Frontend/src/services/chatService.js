import { apiClient } from "./apiClient";

export async function obtenerEstadoChat() {
  const { data } = await apiClient.get("/chat/estado");
  return data;
}

export async function enviarMensajeChat(payload) {
  const { data } = await apiClient.post("/chat/mensajes", payload);
  return data;
}

export async function obtenerHistorialChat(sesionId) {
  const { data } = await apiClient.get(`/chat/sesiones/${encodeURIComponent(sesionId)}`);
  return data;
}
