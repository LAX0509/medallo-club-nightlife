import { apiClient } from "./apiClient";

export async function listarAccesos({ eventoId, page = 1, limit = 20 } = {}) {
  const { data } = await apiClient.get("/accesos", {
    params: { evento_id: eventoId, page, limit },
  });
  return data;
}

export async function obtenerResumenPuerta(eventoId) {
  const { data } = await apiClient.get("/accesos/resumen", { params: { evento_id: eventoId } });
  return data;
}

export async function listarIncidenciasPuerta({ eventoId, limit = 50 } = {}) {
  const { data } = await apiClient.get("/accesos/incidencias", { params: { evento_id: eventoId, limit } });
  return data;
}

export async function registrarIncidenciaPuerta(payload) {
  const { data } = await apiClient.post("/accesos/incidencias", payload);
  return data;
}

export async function registrarAccesoQR({ eventoId, qrCode }) {
  const { data } = await apiClient.post("/accesos", {
    evento_id: eventoId,
    qr_code: qrCode,
    tipo: "qr",
  });
  return data;
}

export async function registrarCortesiaManual({ eventoId, nombreCortesia, justificacion }) {
  const { data } = await apiClient.post("/accesos", {
    evento_id: eventoId,
    tipo: "cortesia_manual",
    nombre_cortesia: nombreCortesia,
    justificacion,
  });
  return data;
}
