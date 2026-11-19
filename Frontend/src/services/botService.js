import { apiClient } from "./apiClient";

export async function obtenerEstadoBot() {
  const { data } = await apiClient.get("/bot/estado");
  return data;
}

export async function obtenerConfiguracionBot() {
  const { data } = await apiClient.get("/bot/configuracion");
  return data;
}

export async function guardarConfiguracionBot(cambios) {
  const { data } = await apiClient.put("/bot/configuracion", cambios);
  return data;
}

export async function probarAsistente({ texto, accion, estado } = {}) {
  const cuerpo = {};
  if (texto) cuerpo.texto = texto;
  if (accion) cuerpo.accion = accion;
  if (estado) cuerpo.estado = estado;
  const { data } = await apiClient.post("/bot/probar", cuerpo);
  return data;
}

export async function probarConexionIA() {
  const { data } = await apiClient.post("/bot/ia/probar");
  return data;
}

export async function probarWhatsApp({ telefono, texto }) {
  const cuerpo = { telefono };
  if (texto) cuerpo.texto = texto;
  const { data } = await apiClient.post("/bot/whatsapp/prueba", cuerpo);
  return data;
}

export async function diagnosticarWhatsApp() {
  const { data } = await apiClient.post("/bot/whatsapp/diagnostico");
  return data;
}
