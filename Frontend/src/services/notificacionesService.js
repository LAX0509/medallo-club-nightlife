import { apiClient } from "./apiClient";

export async function listarNotificaciones({ soloNoLeidas = false, limite = 20 } = {}) {
  const { data } = await apiClient.get("/notificaciones", {
    params: { solo_no_leidas: soloNoLeidas, limite },
  });
  return data;
}

export async function marcarNotificacionLeida(id) {
  const { data } = await apiClient.post(`/notificaciones/${id}/leer`);
  return data;
}

export async function marcarTodasLeidas() {
  const { data } = await apiClient.post("/notificaciones/leer-todas");
  return data;
}
