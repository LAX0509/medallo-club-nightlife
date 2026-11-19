import { apiClient } from "./apiClient";

export async function listarInventario(buscar = "", { categoria = "", estado = "" } = {}) {
  const params = {};
  if (buscar.trim()) params.buscar = buscar.trim();
  if (categoria) params.categoria = categoria;
  if (estado) params.estado = estado;
  const { data } = await apiClient.get("/inventario", {
    params: Object.keys(params).length ? params : undefined,
  });
  return data;
}

export async function crearItemInventario(payload) {
  const { data } = await apiClient.post("/inventario", payload);
  return data;
}

export async function actualizarItemInventario(id, payload) {
  const { data } = await apiClient.put(`/inventario/${id}`, payload);
  return data;
}

export async function eliminarItemInventario(id) {
  await apiClient.delete(`/inventario/${id}`);
}

export async function obtenerResumenInventario() {
  const { data } = await apiClient.get("/inventario/resumen");
  return data;
}

export async function registrarMovimientoInventario(id, payload) {
  const { data } = await apiClient.post(`/inventario/${id}/movimientos`, payload);
  return data;
}

export async function listarHistorialItem(id, limite = 50) {
  const { data } = await apiClient.get(`/inventario/${id}/movimientos`, { params: { limite } });
  return data;
}

export async function listarMovimientosInventario({ tipo = "", eventoId = "", limite = 100 } = {}) {
  const params = { limite };
  if (tipo) params.tipo = tipo;
  if (eventoId) params.evento_id = eventoId;
  const { data } = await apiClient.get("/inventario/movimientos", { params });
  return data;
}

export async function obtenerConsumoEvento(eventoId) {
  const { data } = await apiClient.get(`/inventario/eventos/${eventoId}/consumo`);
  return data;
}

export async function exportarInventarioCsv() {
  const respuesta = await apiClient.get("/inventario/exportar.csv", { responseType: "blob" });
  const url = URL.createObjectURL(respuesta.data);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = "inventario-medallo-club.csv";
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
