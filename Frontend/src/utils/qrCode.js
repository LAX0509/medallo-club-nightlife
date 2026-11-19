// Formatos de QR de Medallo Club. Debe mantenerse en paridad con Backend/app/application/qr_format.py.
//
// El identificador del pase es siempre el código NLD-<evento>-<token>. El QR puede contenerlo de
// varias formas y el sistema reconoce todas al escanear:
//   codigo   -> el código tal cual
//   url      -> enlace público del pase (https://.../pase/<codigo>)
//   esquema  -> enlace profundo medallo://pase/<codigo>
//   json     -> {"app":"medallo-club","v":1,"qr":"<codigo>"}
//   base64   -> cualquiera de los anteriores codificado en base64 / base64url
//   texto    -> texto compartido que incluye el código (p. ej. un mensaje de WhatsApp)

const TOKEN = "NLD-\\d+-[A-Za-z0-9_-]{16,64}";
const QR_PATTERN = new RegExp(`^${TOKEN}$`);
const QR_EMBEBIDO = new RegExp(`(?<![A-Za-z0-9_-])(${TOKEN})(?![A-Za-z0-9_-])`);
const BASE64_PATTERN = /^[A-Za-z0-9+/_-]{24,}={0,2}$/;
const INVISIBLES = /[​‌‍⁠﻿]/g;
const QUERY_KEYS = ["qr", "qr_code", "codigo", "code", "data"];
const MAX_LONGITUD = 2048;

export const FORMATOS_QR = Object.freeze([
  { formato: "codigo", etiqueta: "Código", descripcion: "El código del pase; el más simple y rápido de leer." },
  { formato: "url", etiqueta: "Enlace", descripcion: "Abre la página del pase en cualquier celular." },
  { formato: "esquema", etiqueta: "medallo://", descripcion: "Enlace profundo para la app del equipo." },
  { formato: "json", etiqueta: "JSON", descripcion: "Objeto JSON con versión y código, apto para integraciones." },
  { formato: "base64", etiqueta: "Base64", descripcion: "JSON en base64url, útil si el lector altera símbolos." },
]);

export const ETIQUETA_FORMATO = Object.freeze({
  codigo: "Código",
  url: "Enlace",
  esquema: "medallo://",
  json: "JSON",
  base64: "Base64",
  texto: "Texto compartido",
});

function limpiar(valor) {
  const sinInvisibles = valor.replace(INVISIBLES, "").trim();
  try {
    return decodeURIComponent(sinInvisibles);
  } catch {
    return sinInvisibles;
  }
}

function clavesJson(objeto) {
  const encontrados = QUERY_KEYS.filter((k) => objeto?.[k] && typeof objeto[k] !== "object").map((k) => String(objeto[k]));
  if (objeto?.data && typeof objeto.data === "object") encontrados.push(...clavesJson(objeto.data));
  return encontrados;
}

function desdeUrl(texto) {
  let url;
  try {
    url = new URL(texto);
  } catch {
    return null;
  }
  for (const clave of QUERY_KEYS) {
    const codigo = url.searchParams.get(clave);
    if (codigo && QR_PATTERN.test(codigo.trim())) return { codigo: codigo.trim(), esquema: url.protocol };
  }
  const segmentos = [url.protocol === "medallo:" ? url.host : "", ...url.pathname.split("/")].reverse();
  const codigo = segmentos.find((parte) => QR_PATTERN.test(parte));
  return codigo ? { codigo, esquema: url.protocol } : null;
}

function decodificarBase64(texto) {
  const normal = texto.replace(/-/g, "+").replace(/_/g, "/");
  const relleno = normal + "=".repeat((4 - (normal.length % 4)) % 4);
  try {
    const bytes = Uint8Array.from(atob(relleno), (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
}

function detectar(texto, profundidad) {
  if (QR_PATTERN.test(texto)) return { codigo: texto, formato: "codigo" };

  if (texto.startsWith("{")) {
    try {
      const objeto = JSON.parse(texto);
      const candidato = clavesJson(objeto).find((c) => QR_PATTERN.test(c.trim()));
      if (candidato) return { codigo: candidato.trim(), formato: "json" };
    } catch {
      /* Puede ser otro formato. */
    }
  }

  const enUrl = desdeUrl(texto);
  if (enUrl) return { codigo: enUrl.codigo, formato: enUrl.esquema === "medallo:" ? "esquema" : "url" };

  if (profundidad === 0 && BASE64_PATTERN.test(texto)) {
    const decodificado = decodificarBase64(texto);
    if (decodificado) {
      const interno = detectar(limpiar(decodificado), profundidad + 1);
      if (interno) return { codigo: interno.codigo, formato: "base64" };
    }
  }

  if (texto.slice(0, 4).toLowerCase() === "nld-" && texto.slice(0, 4) !== "NLD-") {
    const corregido = `NLD-${texto.slice(4)}`;
    if (QR_PATTERN.test(corregido)) return { codigo: corregido, formato: "codigo" };
  }

  const embebido = QR_EMBEBIDO.exec(texto);
  return embebido ? { codigo: embebido[1], formato: "texto" } : null;
}

/** Interpreta el contenido de un QR. Devuelve { codigo, formato } o lanza Error si no se reconoce. */
export function detectarFormatoQr(valor) {
  if (typeof valor !== "string") throw new Error("El contenido del QR no es válido.");
  if (valor.length > MAX_LONGITUD) throw new Error("El contenido del QR es demasiado largo.");
  const resultado = detectar(limpiar(valor), 0);
  if (!resultado) throw new Error("Formato QR no reconocido. Usa el código NLD del pase o su enlace/JSON de acceso.");
  return resultado;
}

export function normalizarCodigoQr(valor) {
  return detectarFormatoQr(valor).codigo;
}

/** Id del evento embebido en el código (NLD-<evento>-...), o null. */
export function eventoDeCodigo(codigo) {
  const m = /^NLD-(\d+)-/.exec(codigo || "");
  return m ? Number(m[1]) : null;
}

function base64Url(texto) {
  const bytes = new TextEncoder().encode(texto);
  let binario = "";
  bytes.forEach((b) => {
    binario += String.fromCharCode(b);
  });
  return btoa(binario).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** Texto que se incrusta en el QR para el formato elegido (mismo resultado que el backend). */
export function construirPayloadQr(codigo, formato = "codigo", { baseUrl = window.location.origin, eventoId } = {}) {
  if (!QR_PATTERN.test(codigo)) throw new Error("Código de pase no válido.");
  const base = baseUrl.replace(/\/+$/, "");
  switch (formato) {
    case "codigo":
      return codigo;
    case "url":
      return `${base}/pase/${encodeURIComponent(codigo)}`;
    case "esquema":
      return `medallo://pase/${codigo}`;
    case "json":
    case "base64": {
      const cuerpo = { app: "medallo-club", v: 1, qr: codigo };
      const evento = eventoId ?? eventoDeCodigo(codigo);
      if (evento != null) cuerpo.evento = evento;
      const texto = JSON.stringify(cuerpo);
      return formato === "json" ? texto : base64Url(texto);
    }
    default:
      throw new Error(`Formato de QR no soportado: ${formato}`);
  }
}
