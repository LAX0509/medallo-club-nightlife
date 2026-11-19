import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { esVideoEvento, urlFlyerEvento } from "../services/eventosService";
import { mensajeDeError } from "../services/apiClient";
import {
  copiarTexto,
  fechaLargaEs,
  obtenerPase,
  urlCalendarioPase,
  urlQrPase,
} from "../services/pasesService";
import { FORMATOS_QR } from "../utils/qrCode";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import "./PasePublicoPage.css";

function estadoVisual(pase) {
  if (pase.valido) return { texto: "VÁLIDO", clase: "pase-estado-valido", detalle: "Listo para entrar." };
  if (pase.estado === "usado") return { texto: "YA USADO", clase: "pase-estado-usado", detalle: "Este pase ya fue escaneado en la puerta." };
  return { texto: "NO VÁLIDO", clase: "pase-estado-usado", detalle: "Este pase ya no permite el ingreso." };
}

export function PasePublicoPage() {
  const { codigo } = useParams();
  const [resultado, setResultado] = useState({ codigo: null, pase: null, error: "" });
  const [formato, setFormato] = useState("codigo");
  const [qrFallo, setQrFallo] = useState(false);
  const [aviso, setAviso] = useState("");
  const temporizadorAviso = useRef(null);

  useEffect(() => {
    let vigente = true;
    obtenerPase(codigo)
      .then((datos) => { if (vigente) setResultado({ codigo, pase: datos, error: "" }); })
      .catch((err) => {
        if (!vigente) return;
        const mensaje =
          err?.response?.status === 404
            ? "Este pase no existe o ya no está disponible."
            : mensajeDeError(err, "No pudimos cargar tu pase. Revisa tu conexión e inténtalo de nuevo.");
        setResultado({ codigo, pase: null, error: mensaje });
      });
    return () => { vigente = false; };
  }, [codigo]);

  const cargando = resultado.codigo !== codigo;
  const { pase, error } = cargando ? { pase: null, error: "" } : resultado;

  useEffect(() => () => window.clearTimeout(temporizadorAviso.current), []);

  function mostrarAviso(texto) {
    setAviso(texto);
    window.clearTimeout(temporizadorAviso.current);
    temporizadorAviso.current = window.setTimeout(() => setAviso(""), 2500);
  }

  async function copiarEnlace() {
    const enlace = `${window.location.origin}/pase/${encodeURIComponent(pase.codigo)}`;
    mostrarAviso((await copiarTexto(enlace)) ? "Enlace del pase copiado." : "No pudimos copiar el enlace. Cópialo desde la barra del navegador.");
  }

  function elegirFormato(valor) {
    setFormato(valor);
    setQrFallo(false);
  }

  const descripcionFormato = FORMATOS_QR.find((f) => f.formato === formato)?.descripcion ?? "";

  return (
    <main className="pase-pagina">
      <header className="pase-cabecera pase-noprint">
        <Link className="pase-marca" to="/" aria-label="Medallo Club, inicio">
          <img src={medalloLogo} alt="" />
          <span><strong>MEDALLO CLUB</strong><small>Pase digital</small></span>
        </Link>
      </header>

      {cargando && <p className="pase-mensaje" role="status">Cargando tu pase…</p>}

      {!cargando && error && (
        <section className="pase-mensaje pase-mensaje-error card" role="alert">
          <strong>{error}</strong>
          <p>Si crees que es un error, pídele a quien te lo envió que te comparta el enlace de nuevo.</p>
          <Link className="btn btn-outline btn-sm" to="/">Ir al inicio</Link>
        </section>
      )}

      {!cargando && pase && (
        <>
          <article className="pase-boleta" aria-label={`Pase de ingreso de ${pase.nombre}`}>
            {pase.flyer_url && (
              <div className="pase-flyer-wrap pase-noprint">
                {esVideoEvento(pase.flyer_url) ? (
                  <video className="pase-flyer" src={urlFlyerEvento(pase.flyer_url)} muted loop playsInline autoPlay />
                ) : (
                  <img className="pase-flyer" src={urlFlyerEvento(pase.flyer_url)} alt={`Flyer de ${pase.evento_nombre}`} />
                )}
              </div>
            )}

            <div className={`pase-estado ${estadoVisual(pase).clase}`} role="status">
              <strong>{estadoVisual(pase).texto}</strong>
              <span>{estadoVisual(pase).detalle}</span>
            </div>

            <div className="pase-cuerpo">
              <p className="pase-kicker">Pase de ingreso</p>
              <h1>{pase.nombre}</h1>
              <p className="pase-evento">{pase.evento_nombre}</p>
              <p className="pase-fecha">{fechaLargaEs(pase.evento_fecha)}</p>
              {pase.evento_tematica && <p className="pase-tematica">Temática: {pase.evento_tematica}</p>}

              <div className="pase-qr">
                {qrFallo ? (
                  <p role="alert">No pudimos cargar el QR. Revisa tu conexión y recarga la página.</p>
                ) : (
                  <img
                    key={formato}
                    src={urlQrPase(pase.codigo, { extension: "svg", formato })}
                    alt={`Código QR del pase de ${pase.nombre}, formato ${formato}`}
                    onError={() => setQrFallo(true)}
                  />
                )}
              </div>
              <code className="pase-codigo">{pase.codigo}</code>

              {pase.reserva && (
                <section className="pase-garantia" aria-label="Reserva garantizada">
                  <p className="pase-garantia-etiqueta">
                    {pase.reserva.codigo_garantia ? "Reserva garantizada" : "Reserva"} · {pase.reserva.tipo === "palco" ? "Palco" : "Mesa"}
                  </p>
                  {pase.reserva.codigo_garantia && <code>{pase.reserva.codigo_garantia}</code>}
                  <dl>
                    {pase.reserva.ubicacion_asignada && (
                      <div><dt>Ubicación</dt><dd>{pase.reserva.ubicacion_asignada}</dd></div>
                    )}
                    {pase.reserva.hora_limite && (
                      <div><dt>Llega antes de las</dt><dd>{pase.reserva.hora_limite}</dd></div>
                    )}
                  </dl>
                </section>
              )}
            </div>
          </article>

          <section className="pase-controles pase-noprint" aria-label="Opciones del pase">
            <p className="pase-brillo">Sube el brillo de tu pantalla al llegar a la puerta.</p>

            <fieldset className="pase-formatos">
              <legend>Formato del QR</legend>
              <div className="pase-formatos-grupo">
                {FORMATOS_QR.map((f) => (
                  <label key={f.formato} className={formato === f.formato ? "activo" : ""}>
                    <input
                      type="radio"
                      name="formato-qr"
                      value={f.formato}
                      checked={formato === f.formato}
                      onChange={() => elegirFormato(f.formato)}
                    />
                    <span>{f.etiqueta}</span>
                  </label>
                ))}
              </div>
              <p className="pase-formato-descripcion" aria-live="polite">{descripcionFormato}</p>
            </fieldset>

            <div className="pase-acciones">
              <a className="btn btn-primary" href={urlQrPase(pase.codigo, { extension: "png", formato, descargar: true })} download>
                Descargar PNG
              </a>
              <a className="btn btn-outline" href={urlQrPase(pase.codigo, { extension: "svg", formato, descargar: true })} download>
                Descargar SVG
              </a>
              <a className="btn btn-outline" href={urlCalendarioPase(pase.codigo)}>Agregar al calendario</a>
              <button className="btn btn-outline" type="button" onClick={() => window.print()}>Imprimir / guardar PDF</button>
              <button className="btn btn-outline" type="button" onClick={copiarEnlace}>Copiar enlace del pase</button>
            </div>
            <p className="pase-aviso" role="status" aria-live="polite">{aviso}</p>
          </section>
        </>
      )}
    </main>
  );
}
