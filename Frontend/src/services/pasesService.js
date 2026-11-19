import { apiClient } from "./apiClient";

export async function obtenerPase(codigo) {
  const { data } = await apiClient.get(`/pases/${encodeURIComponent(codigo)}`);
  return data;
}

/** URL absoluta de la imagen QR del servidor. extension: "svg" | "png". */
export function urlQrPase(codigo, { extension = "svg", formato = "codigo", descargar = false } = {}) {
  const parametros = new URLSearchParams({ formato });
  if (descargar) parametros.set("descargar", "true");
  return `${apiClient.defaults.baseURL}/pases/${encodeURIComponent(codigo)}/qr.${extension}?${parametros.toString()}`;
}

export function urlCalendarioPase(codigo) {
  return `${apiClient.defaults.baseURL}/pases/${encodeURIComponent(codigo)}/calendario.ics`;
}

export async function listarFormatosQr() {
  const { data } = await apiClient.get("/qr/formatos");
  return data;
}

export async function consultarMiReserva(id, token) {
  const { data } = await apiClient.post(`/reservas/${id}/mi-reserva`, { token_cancelacion: token });
  return data;
}

export async function cancelarMiReserva(id, token) {
  const { data } = await apiClient.post(`/reservas/${id}/cancelar`, { token_cancelacion: token });
  return data;
}

/** Fecha ISO (AAAA-MM-DD) en español largo: "sábado, 25 de octubre de 2026". */
export function fechaLargaEs(fecha) {
  if (!fecha) return "";
  const valor = new Date(`${String(fecha).slice(0, 10)}T12:00:00`);
  if (Number.isNaN(valor.getTime())) return String(fecha);
  const texto = valor.toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** Copia texto al portapapeles; devuelve true si lo logró (con respaldo si no existe la API moderna). */
export async function copiarTexto(texto) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(texto);
      return true;
    }
  } catch {
    /* Se intenta el respaldo. */
  }
  const campo = document.createElement("textarea");
  campo.value = texto;
  campo.setAttribute("readonly", "");
  campo.style.position = "fixed";
  campo.style.opacity = "0";
  document.body.appendChild(campo);
  campo.select();
  campo.setSelectionRange(0, texto.length);
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    document.body.removeChild(campo);
  }
}
