import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { esVideoEvento, urlFlyerEvento } from "../services/eventosService";
import { mensajeDeError } from "../services/apiClient";
import {
  cancelarMiReserva,
  consultarMiReserva,
  copiarTexto,
  fechaLargaEs,
  urlQrPase,
} from "../services/pasesService";
import "./MiReservaVista.css";

const INTERVALO_SONDEO_MS = 20000;
const FORMATO_COP = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });

const ESTADOS = {
  pendiente: { etiqueta: "En validación", clase: "badge-accent" },
  confirmada: { etiqueta: "Confirmada", clase: "badge-success" },
  cancelada: { etiqueta: "Cancelada", clase: "badge-danger" },
};

export function MiReservaVista({ id, token }) {
  const [reserva, setReserva] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [cancelando, setCancelando] = useState(false);
  const [errorCancelar, setErrorCancelar] = useState("");
  const [copiado, setCopiado] = useState(false);
  const temporizadorCopia = useRef(null);

  const cargar = useCallback(
    async ({ silencioso = false } = {}) => {
      try {
        const datos = await consultarMiReserva(id, token);
        setReserva(datos);
        setError("");
      } catch (err) {
        if (silencioso) return;
        setReserva(null);
        setError(
          err?.response?.status === 404
            ? "Este enlace no es válido o la reserva ya no está disponible. Revisa que lo hayas copiado completo."
            : mensajeDeError(err, "No pudimos cargar tu reserva. Revisa tu conexión e inténtalo de nuevo.")
        );
      } finally {
        if (!silencioso) setCargando(false);
      }
    },
    [id, token]
  );

  useEffect(() => {
    cargar();
  }, [cargar]);

  const pendiente = reserva?.estado === "pendiente";
  useEffect(() => {
    if (!pendiente) return undefined;
    const intervalo = window.setInterval(() => cargar({ silencioso: true }), INTERVALO_SONDEO_MS);
    return () => window.clearInterval(intervalo);
  }, [pendiente, cargar]);

  useEffect(() => () => window.clearTimeout(temporizadorCopia.current), []);

  async function cancelar() {
    if (!window.confirm("¿Seguro que quieres cancelar esta reserva? Esta acción no se puede deshacer.")) return;
    setCancelando(true);
    setErrorCancelar("");
    try {
      await cancelarMiReserva(id, token);
      await cargar({ silencioso: true });
    } catch (err) {
      setErrorCancelar(mensajeDeError(err, "No pudimos cancelar la reserva. Inténtalo de nuevo."));
    } finally {
      setCancelando(false);
    }
  }

  async function copiarCodigo() {
    if (!(await copiarTexto(reserva.codigo_garantia))) return;
    setCopiado(true);
    window.clearTimeout(temporizadorCopia.current);
    temporizadorCopia.current = window.setTimeout(() => setCopiado(false), 2000);
  }

  if (cargando) {
    return (
      <section className="mireserva card" aria-busy="true">
        <p className="mireserva-estado-carga" role="status">Buscando tu reserva…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mireserva card">
        <div className="mireserva-final" role="alert">
          <strong>No pudimos mostrar tu reserva</strong>
          <p>{error}</p>
          <button className="btn btn-outline btn-sm" type="button" onClick={() => { setCargando(true); cargar(); }}>
            Reintentar
          </button>
        </div>
      </section>
    );
  }

  const estado = ESTADOS[reserva.estado] ?? { etiqueta: reserva.estado, clase: "badge-neutral" };
  const flyer = urlFlyerEvento(reserva.flyer_url);
  const tipo = reserva.tipo === "palco" ? "Palco" : "Mesa";
  const consumo =
    reserva.consumo_minimo != null && Number(reserva.consumo_minimo) > 0
      ? FORMATO_COP.format(Number(reserva.consumo_minimo))
      : null;

  return (
    <section className="mireserva" aria-label={`Reserva número ${reserva.id}`}>
      <div className="mireserva-cabecera">
        <div>
          <p className="mireserva-kicker">Tu reserva</p>
          <h2>Reserva #{reserva.id}</h2>
          {reserva.nombre_cliente && <p className="mireserva-cliente">A nombre de {reserva.nombre_cliente}</p>}
        </div>
        <span className={`badge ${estado.clase}`}>{estado.etiqueta}</span>
      </div>

      <article className="mireserva-evento card">
        {flyer &&
          (esVideoEvento(reserva.flyer_url) ? (
            <video className="mireserva-flyer" src={flyer} muted loop playsInline autoPlay aria-label={`Flyer de ${reserva.evento_nombre}`} />
          ) : (
            <img className="mireserva-flyer" src={flyer} alt={`Flyer de ${reserva.evento_nombre}`} loading="lazy" />
          ))}
        <div className="mireserva-evento-datos">
          <h3>{reserva.evento_nombre}</h3>
          <p className="mireserva-fecha">{fechaLargaEs(reserva.evento_fecha)}</p>
          {reserva.evento_tematica && <p className="mireserva-tematica">Temática: {reserva.evento_tematica}</p>}
          <ul className="mireserva-resumen">
            <li><span>Reservaste</span><strong>{tipo}</strong></li>
            <li><span>Personas</span><strong>{reserva.asistentes}</strong></li>
          </ul>
        </div>
      </article>

      {pendiente && (
        <div className="mireserva-aviso" role="status" aria-live="polite">
          <span className="mireserva-pulso" aria-hidden="true" />
          <p>El equipo está validando el cupo; esta página se actualiza sola. No necesitas recargarla.</p>
        </div>
      )}

      {reserva.estado === "cancelada" && (
        <div className="mireserva-final mireserva-cancelada" role="status">
          <strong>Esta reserva fue cancelada</strong>
          <p>Ya no hay cupo ni pases activos para esta solicitud. Si cambias de planes, puedes hacer una nueva en el asistente.</p>
          <Link className="btn btn-outline btn-sm" to="/reservas">Hacer una nueva reserva</Link>
        </div>
      )}

      {reserva.garantizada && (
        <section className="mireserva-garantia" aria-label="Reserva garantizada">
          <p className="mireserva-garantia-etiqueta">Reserva garantizada</p>
          <div className="mireserva-garantia-codigo">
            <code>{reserva.codigo_garantia}</code>
            <button className="btn btn-outline btn-sm" type="button" onClick={copiarCodigo} aria-live="polite">
              {copiado ? "Copiado" : "Copiar código"}
            </button>
          </div>
          <dl className="mireserva-garantia-datos">
            {reserva.hora_limite && (
              <div><dt>Hora límite</dt><dd>Llega antes de las {reserva.hora_limite}</dd></div>
            )}
            {reserva.ubicacion_asignada && (
              <div><dt>Tu ubicación</dt><dd>{reserva.ubicacion_asignada}</dd></div>
            )}
            {consumo && (
              <div><dt>Consumo mínimo</dt><dd>{consumo}</dd></div>
            )}
          </dl>
          <p className="mireserva-garantia-ayuda">Presenta este código o tus pases QR en la puerta.</p>
        </section>
      )}

      {reserva.pases?.length > 0 && (
        <section className="mireserva-pases" aria-labelledby="mireserva-pases-titulo">
          <h3 id="mireserva-pases-titulo">Pases de ingreso</h3>
          <ul className="mireserva-pases-grid">
            {reserva.pases.map((pase) => (
              <li key={pase.id} className="mireserva-pase card">
                <div className="mireserva-pase-cabecera">
                  <strong>{pase.nombre}</strong>
                  <span className={`badge ${pase.estado === "usado" ? "badge-danger" : "badge-success"}`}>
                    {pase.estado === "usado" ? "Usado" : "Por usar"}
                  </span>
                </div>
                <div className="mireserva-qr">
                  <img
                    src={urlQrPase(pase.qr_code, { extension: "svg" })}
                    alt={`Código QR de ingreso de ${pase.nombre}`}
                    loading="lazy"
                    width="180"
                    height="180"
                  />
                </div>
                <div className="mireserva-pase-acciones">
                  <Link className="btn btn-primary btn-sm" to={`/pase/${encodeURIComponent(pase.qr_code)}`}>Abrir pase</Link>
                  <a
                    className="btn btn-outline btn-sm"
                    href={urlQrPase(pase.qr_code, { extension: "png", descargar: true })}
                    download
                  >
                    Descargar PNG
                  </a>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {reserva.puede_cancelar && (
        <div className="mireserva-cancelar">
          {errorCancelar && <p className="mireserva-error" role="alert">{errorCancelar}</p>}
          <button className="btn btn-danger btn-sm" type="button" onClick={cancelar} disabled={cancelando}>
            {cancelando ? "Cancelando…" : "Cancelar reserva"}
          </button>
        </div>
      )}
    </section>
  );
}
