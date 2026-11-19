import { apiClient } from "./apiClient";

export async function listarEventos({ page = 1, limit = 50 } = {}) {
  const { data } = await apiClient.get("/eventos", { params: { page, limit } });
  return data;
}

export async function obtenerEvento(id) {
  const { data } = await apiClient.get(`/eventos/${id}`);
  return data;
}

export async function crearEvento(payload) {
  const { data } = await apiClient.post("/eventos", payload);
  return data;
}

const TAMANO_PARTE = 3_500_000; // cada solicitud del hosting admite ~4,5 MB

export async function cargarFlyerEvento(id, archivo, alAvanzar) {
  const total = Math.max(1, Math.ceil(archivo.size / TAMANO_PARTE));
  const subida = (globalThis.crypto?.randomUUID?.() ?? `${Date.now()}${Math.random()}`.replace(/\D/g, "")).replace(/-/g, "").slice(0, 32);
  let ultimo = null;
  for (let orden = 0; orden < total; orden += 1) {
    const trozo = archivo.slice(orden * TAMANO_PARTE, (orden + 1) * TAMANO_PARTE);
    const formulario = new FormData();
    formulario.append("subida", subida);
    formulario.append("orden", String(orden));
    formulario.append("total", String(total));
    formulario.append("tipo", archivo.type);
    formulario.append("tamano_total", String(archivo.size));
    formulario.append("archivo", trozo, archivo.name);
    const { data } = await apiClient.post(`/eventos/${id}/flyer/partes`, formulario);
    ultimo = data;
    alAvanzar?.(Math.round(((orden + 1) / total) * 100));
  }
  return ultimo;
}

export async function eliminarFlyerEvento(id) {
  const { data } = await apiClient.delete(`/eventos/${id}/flyer`);
  return data;
}

export function urlFlyerEvento(ruta) {
  if (!ruta) return "";
  if (/^https?:\/\//i.test(ruta)) return ruta;
  try {
    const origenApi = new URL(apiClient.defaults.baseURL).origin;
    return new URL(ruta, origenApi).toString();
  } catch {
    return ruta;
  }
}

export function esVideoEvento(ruta) {
  return /\.(mp4|webm)(?:$|\?)/i.test(ruta ?? "");
}

export async function actualizarEvento(id, payload) {
  const { data } = await apiClient.put(`/eventos/${id}`, payload);
  return data;
}

export async function eliminarEvento(id) {
  await apiClient.delete(`/eventos/${id}`);
}
