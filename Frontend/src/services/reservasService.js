import { apiClient } from "./apiClient";

export async function listarEventosParaReservas() {
  const { data } = await apiClient.get("/reservas/eventos");
  return data;
}

export async function crearSolicitudReserva(payload) {
  const { data } = await apiClient.post("/reservas", payload);
  return data;
}

export async function cancelarSolicitudCliente(id, tokenCancelacion) {
  const { data } = await apiClient.post(`/reservas/${id}/cancelar`, {
    token_cancelacion: tokenCancelacion,
  });
  return data;
}

export async function listarSolicitudesReserva() {
  const { data } = await apiClient.get("/reservas");
  return data;
}

export async function listarReservasReferidas() {
  const { data } = await apiClient.get("/reservas/mis-referidas");
  return data;
}

/**
 * Cambia el estado de una reserva. Al confirmar (garantizar) se pueden enviar las condiciones:
 * { ubicacion_asignada, hora_limite ('HH:MM'), consumo_minimo, forzar_cupo }.
 */
export async function actualizarEstadoReserva(id, estado, extra = {}) {
  const { data } = await apiClient.patch(`/reservas/${id}/estado`, { ...extra, estado });
  return data;
}

export async function listarPasesDeReserva(id) {
  const { data } = await apiClient.get(`/reservas/${id}/pases`);
  return data;
}

export async function reenviarConfirmacionReserva(id) {
  const { data } = await apiClient.post("/reservas/" + id + "/reenviar-confirmacion");
  return data;
}

export async function eliminarReservaCancelada(id) {
  await apiClient.delete(`/reservas/${id}`);
}
