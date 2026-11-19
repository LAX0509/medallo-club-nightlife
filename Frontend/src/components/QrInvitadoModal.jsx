import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";
import { copiarTexto } from "../services/pasesService";
import { FORMATOS_QR, construirPayloadQr } from "../utils/qrCode";
import "./QrInvitadoModal.css";

export function QrInvitadoModal({ invitado, onClose }) {
  const [formato, setFormato] = useState("codigo");
  const [generado, setGenerado] = useState({ payload: "", imagen: "", imagenSvg: "", error: "" });
  const [aviso, setAviso] = useState("");
  const botonCerrar = useRef(null);
  const temporizadorAviso = useRef(null);

  const { payload, errorPayload } = useMemo(() => {
    try {
      return { payload: construirPayloadQr(invitado.qr_code, formato), errorPayload: "" };
    } catch (err) {
      return { payload: "", errorPayload: err.message };
    }
  }, [invitado.qr_code, formato]);

  useEffect(() => {
    if (!payload) return undefined;
    let vigente = true;
    Promise.allSettled([
      QRCode.toString(payload, { type: "svg", errorCorrectionLevel: "M", margin: 2 }),
      QRCode.toDataURL(payload, {
        errorCorrectionLevel: "M",
        margin: 2,
        width: 360,
        color: { dark: "#07101e", light: "#ffffff" },
      }),
    ]).then(([svg, png]) => {
      if (!vigente) return;
      setGenerado({
        payload,
        imagen: png.status === "fulfilled" ? png.value : "",
        imagenSvg: svg.status === "fulfilled" ? "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg.value) : "",
        error: png.status === "rejected" ? "No se pudo generar la imagen QR. Inténtalo de nuevo." : "",
      });
    });
    return () => { vigente = false; };
  }, [payload]);

  const actual = payload && generado.payload === payload ? generado : null;
  const imagen = actual?.imagen ?? "";
  const imagenSvg = actual?.imagenSvg ?? "";
  const error = errorPayload || actual?.error || "";

  useEffect(() => {
    function cerrarConEscape(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", cerrarConEscape);
    return () => window.removeEventListener("keydown", cerrarConEscape);
  }, [onClose]);

  useEffect(() => {
    botonCerrar.current?.focus();
    return () => window.clearTimeout(temporizadorAviso.current);
  }, []);

  const nombreArchivo = (invitado.nombre || "invitado")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "") || "invitado";
  const sufijoFormato = formato === "codigo" ? "" : `-${formato}`;
  const enlacePase = `${window.location.origin}/pase/${encodeURIComponent(invitado.qr_code)}`;
  const descripcionFormato = FORMATOS_QR.find((f) => f.formato === formato)?.descripcion ?? "";

  async function copiar(texto, confirmacion) {
    const logrado = await copiarTexto(texto);
    setAviso(logrado ? confirmacion : "No se pudo copiar. Selecciónalo y cópialo manualmente.");
    window.clearTimeout(temporizadorAviso.current);
    temporizadorAviso.current = window.setTimeout(() => setAviso(""), 2500);
  }

  return (
    <div className="qr-modal-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="qr-modal card" role="dialog" aria-modal="true" aria-labelledby="qr-modal-title">
        <button ref={botonCerrar} className="qr-modal-close" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        <p className="section-kicker">PASE DE INGRESO</p>
        <h2 id="qr-modal-title">{invitado.nombre}</h2>
        <p className="qr-modal-help">Muestra este código en la entrada para que el personal de Puerta lo escanee.</p>

        <fieldset className="qr-modal-formatos">
          <legend>Formato del QR</legend>
          <div className="qr-modal-formatos-grupo">
            {FORMATOS_QR.map((f) => (
              <label key={f.formato} className={formato === f.formato ? "activo" : ""}>
                <input
                  type="radio"
                  name={`formato-qr-${invitado.id ?? invitado.qr_code}`}
                  value={f.formato}
                  checked={formato === f.formato}
                  onChange={() => setFormato(f.formato)}
                />
                <span>{f.etiqueta}</span>
              </label>
            ))}
          </div>
          <p className="qr-modal-formato-descripcion" aria-live="polite">{descripcionFormato}</p>
        </fieldset>

        <div className="qr-modal-image-wrap">
          {imagen ? <img src={imagen} alt={`Código QR de ingreso para ${invitado.nombre}`} /> : error ? <p role="alert">{error}</p> : <p>Generando QR…</p>}
        </div>
        <code className="qr-modal-code">{invitado.qr_code}</code>

        <div className="qr-modal-actions">
          {imagen && <a className="btn btn-primary" href={imagen} download={"medallo-club-" + nombreArchivo + sufijoFormato + ".png"}>Descargar PNG</a>}
          {imagenSvg && <a className="btn btn-outline" href={imagenSvg} download={"medallo-club-" + nombreArchivo + sufijoFormato + ".svg"}>Descargar SVG</a>}
        </div>
        <div className="qr-modal-actions qr-modal-actions-secundarias">
          <button className="btn btn-outline btn-sm" type="button" onClick={() => copiar(invitado.qr_code, "Código copiado.")}>Copiar código</button>
          <button className="btn btn-outline btn-sm" type="button" onClick={() => copiar(enlacePase, "Enlace del pase copiado.")}>Copiar enlace del pase</button>
          <a className="btn btn-outline btn-sm" href={enlacePase} target="_blank" rel="noopener noreferrer">Abrir página del pase</a>
        </div>
        <p className="qr-modal-aviso" role="status" aria-live="polite">{aviso}</p>
        <button className="btn btn-outline" type="button" onClick={onClose}>Cerrar</button>
      </section>
    </div>
  );
}
