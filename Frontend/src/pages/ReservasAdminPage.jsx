import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner";
import { Badge } from "../components/Badge";
import { apiClient, mensajeDeError } from "../services/apiClient";
import {
  actualizarEstadoReserva,
  eliminarReservaCancelada,
  listarPasesDeReserva,
  listarSolicitudesReserva,
  reenviarConfirmacionReserva,
} from "../services/reservasService";
import "./ReservasAdminPage.css";

function fechaHora(fecha) {
  return new Date(fecha).toLocaleString("es-CO", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function pesos(valor) {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return null;
  return numero.toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
}

const varianteEstado = { pendiente: "accent", confirmada: "success", cancelada: "neutral" };
const textoEstadoWhatsApp = {
  sin_configurar: "sin configurar",
  enviada: "aceptada por Meta; esperando entrega",
  entregada: "entregada",
  leida: "leída",
  fallida: "fallida",
};
const puedeReintentarWhatsApp = (estado) => ["sin_configurar", "fallida"].includes(estado);

const HORA_LIMITE_POR_DEFECTO = "23:30";
const UBICACIONES_SUGERIDAS = [
  "Mesa 1", "Mesa 2", "Mesa 3", "Mesa 4", "Mesa 5", "Mesa 6",
  "Palco VIP 1", "Palco VIP 2", "Palco VIP 3", "Terraza", "Barra", "Zona VIP",
];
const FILTROS = [
  { clave: "todas", etiqueta: "Todas" },
  { clave: "pendientes", etiqueta: "Pendientes" },
  { clave: "garantizadas", etiqueta: "Garantizadas" },
  { clave: "canceladas", etiqueta: "Canceladas" },
];
const ESTADO_POR_FILTRO = { pendientes: "pendiente", garantizadas: "confirmada", canceladas: "cancelada" };
const SELECTOR_ENFOCABLE = 'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

const urlPase = (codigo) => `${window.location.origin}/pase/${encodeURIComponent(codigo)}`;
const urlQrPase = (codigo) => `${apiClient.defaults.baseURL}/pases/${encodeURIComponent(codigo)}/qr.svg`;

async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    const campo = document.createElement("textarea");
    campo.value = texto;
    campo.setAttribute("readonly", "");
    campo.style.position = "fixed";
    campo.style.opacity = "0";
    document.body.appendChild(campo);
    campo.select();
    let copiado = false;
    try { copiado = document.execCommand("copy"); } catch { copiado = false; }
    document.body.removeChild(campo);
    return copiado;
  }
}

/** Foco inicial, atrapa el tabulador, cierra con Escape y devuelve el foco al abrir/cerrar. */
function useDialogo(contenedorRef, onClose) {
  const onCloseRef = useRef(onClose);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);

  useEffect(() => {
    const previo = document.activeElement;
    const contenedor = contenedorRef.current;
    const inicial = contenedor?.querySelector("[data-foco-inicial]") ?? contenedor?.querySelector(SELECTOR_ENFOCABLE);
    inicial?.focus();

    function alPulsarTecla(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !contenedor) return;
      const enfocables = [...contenedor.querySelectorAll(SELECTOR_ENFOCABLE)];
      if (enfocables.length === 0) return;
      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];
      if (event.shiftKey && document.activeElement === primero) {
        event.preventDefault();
        ultimo.focus();
      } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primero.focus();
      }
    }

    document.addEventListener("keydown", alPulsarTecla);
    return () => {
      document.removeEventListener("keydown", alPulsarTecla);
      if (previo instanceof HTMLElement && document.contains(previo)) previo.focus();
    };
  }, [contenedorRef]);
}

function GarantizarModal({ reserva, onClose, onGarantizada }) {
  const ref = useRef(null);
  const [ubicacion, setUbicacion] = useState(reserva.ubicacion_asignada ?? "");
  const [horaLimite, setHoraLimite] = useState(reserva.hora_limite || HORA_LIMITE_POR_DEFECTO);
  const [consumo, setConsumo] = useState(reserva.consumo_minimo != null ? String(Number(reserva.consumo_minimo)) : "");
  const [forzarCupo, setForzarCupo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);
  const [sinCupo, setSinCupo] = useState(false);
  const cerrar = useCallback(() => { if (!enviando) onClose(); }, [enviando, onClose]);
  useDialogo(ref, cerrar);

  async function enviar(event) {
    event.preventDefault();
    setEnviando(true);
    setError(null);
    const extra = { forzar_cupo: sinCupo && forzarCupo };
    if (ubicacion.trim()) extra.ubicacion_asignada = ubicacion.trim();
    if (horaLimite) extra.hora_limite = horaLimite;
    if (consumo !== "") extra.consumo_minimo = Number(consumo);
    try {
      const actualizada = await actualizarEstadoReserva(reserva.id, "confirmada", extra);
      onGarantizada(actualizada);
    } catch (err) {
      setSinCupo(err?.response?.status === 409);
      setForzarCupo(false);
      setError(mensajeDeError(err, "No fue posible garantizar la reserva."));
      setEnviando(false);
    }
  }

  return (
    <div className="reservas-modal-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) cerrar(); }}>
      <section ref={ref} className="reservas-modal card" role="dialog" aria-modal="true" aria-labelledby="garantizar-titulo">
        <button className="reservas-modal-cerrar" type="button" onClick={cerrar} aria-label="Cerrar" disabled={enviando}>×</button>
        <p className="section-kicker">RESERVA GARANTIZADA</p>
        <h2 id="garantizar-titulo">Garantizar reserva</h2>
        <dl className="reservas-modal-resumen">
          <div><dt>Cliente</dt><dd>{reserva.nombre_cliente}</dd></div>
          <div><dt>Evento</dt><dd>{reserva.evento_nombre}</dd></div>
          <div><dt>Tipo</dt><dd>{reserva.tipo === "mesa" ? "Mesa" : "Palco"}</dd></div>
          <div><dt>Personas</dt><dd>{reserva.asistentes}</dd></div>
        </dl>
        <p className="reservas-modal-pases">Se emitirán <strong>{reserva.asistentes} {reserva.asistentes === 1 ? "pase QR" : "pases QR"}</strong>, uno por asistente.</p>

        <form onSubmit={enviar}>
          <div className="form-field">
            <label htmlFor="garantia-ubicacion">Ubicación asignada</label>
            <input id="garantia-ubicacion" data-foco-inicial list="garantia-ubicaciones" maxLength={60} value={ubicacion} onChange={(event) => setUbicacion(event.target.value)} placeholder="Ej.: Mesa 4 o Palco VIP 1" autoComplete="off" />
            <datalist id="garantia-ubicaciones">{UBICACIONES_SUGERIDAS.map((opcion) => <option key={opcion} value={opcion} />)}</datalist>
          </div>
          <div className="reservas-modal-fila">
            <div className="form-field">
              <label htmlFor="garantia-hora">Hora límite de llegada</label>
              <input id="garantia-hora" type="time" value={horaLimite} onChange={(event) => setHoraLimite(event.target.value)} />
            </div>
            <div className="form-field">
              <label htmlFor="garantia-consumo">Consumo mínimo (COP, opcional)</label>
              <input id="garantia-consumo" type="number" inputMode="numeric" min="0" step="1000" value={consumo} onChange={(event) => setConsumo(event.target.value)} placeholder="Ej.: 500000" />
            </div>
          </div>

          {error && <div className="reservas-modal-error" role="alert">{error}</div>}
          {sinCupo && (
            <label className="reservas-modal-forzar">
              <input type="checkbox" checked={forzarCupo} onChange={(event) => setForzarCupo(event.target.checked)} />
              <span>Autorizo exceder el cupo del evento</span>
            </label>
          )}

          <div className="reservas-modal-acciones">
            <button className="btn btn-outline" type="button" onClick={cerrar} disabled={enviando}>Volver</button>
            <button className="btn btn-primary" type="submit" disabled={enviando || (sinCupo && !forzarCupo)}>
              {enviando ? "Garantizando…" : sinCupo ? "Garantizar excediendo cupo" : "Garantizar reserva"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function PasesModal({ reserva, onClose }) {
  const ref = useRef(null);
  const [pases, setPases] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState("");
  useDialogo(ref, onClose);

  async function copiarEnlace(pase) {
    const copiado = await copiarTexto(urlPase(pase.qr_code));
    setAviso(copiado ? `Enlace del pase de ${pase.nombre} copiado.` : "No se pudo copiar automáticamente. Usa el botón Abrir y copia la dirección.");
  }

  const cargar = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      setPases(await listarPasesDeReserva(reserva.id));
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar los pases."));
    } finally {
      setCargando(false);
    }
  }, [reserva.id]);

  useEffect(() => { cargar(); }, [cargar]);

  return (
    <div className="reservas-modal-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={ref} className="reservas-modal reservas-modal-ancho card" role="dialog" aria-modal="true" aria-labelledby="pases-titulo">
        <button className="reservas-modal-cerrar" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        <p className="section-kicker">PASES QR</p>
        <h2 id="pases-titulo">Pases de {reserva.nombre_cliente}</h2>
        <p className="reservas-modal-ayuda">{reserva.evento_nombre}{reserva.codigo_garantia ? ` · ${reserva.codigo_garantia}` : ""}</p>

        {cargando ? <p className="reservas-admin-empty">Cargando pases…</p> : error ? (
          <div className="reservas-modal-error" role="alert">{error} <button className="btn btn-outline btn-sm" type="button" onClick={cargar}>Reintentar</button></div>
        ) : pases.length === 0 ? (
          <p className="reservas-admin-empty">Esta reserva todavía no tiene pases emitidos.</p>
        ) : (
          <ul className="reservas-pases-lista">
            {pases.map((pase) => (
              <li key={pase.id} className="reservas-pase">
                <img className="reservas-pase-qr" src={urlQrPase(pase.qr_code)} alt={`QR del pase de ${pase.nombre}`} width="64" height="64" loading="lazy" />
                <div className="reservas-pase-datos">
                  <strong>{pase.nombre}</strong>
                  <code>{pase.qr_code}</code>
                  <Badge variante={pase.estado === "usado" ? "success" : "accent"}>{pase.estado === "usado" ? "Usado" : "Por usar"}</Badge>
                </div>
                <div className="reservas-pase-acciones">
                  <button className="btn btn-outline btn-sm" type="button" onClick={() => copiarEnlace(pase)}>Copiar enlace del pase</button>
                  <a className="btn btn-outline btn-sm" href={urlPase(pase.qr_code)} target="_blank" rel="noreferrer">Abrir ↗</a>
                </div>
              </li>
            ))}
          </ul>
        )}

        {aviso && <p className="reservas-modal-aviso" role="status">{aviso}</p>}
        <div className="reservas-modal-acciones">
          <button className="btn btn-primary" type="button" onClick={onClose}>Cerrar</button>
        </div>
      </section>
    </div>
  );
}

export function ReservasAdminPage() {
  const location = useLocation();
  const [reservas, setReservas] = useState([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [actualizandoId, setActualizandoId] = useState(null);
  const [mensaje, setMensaje] = useState("");
  const [filtro, setFiltro] = useState("todas");
  const [busqueda, setBusqueda] = useState("");
  const [reservaAGarantizar, setReservaAGarantizar] = useState(null);
  const [reservaConPases, setReservaConPases] = useState(null);
  const [destacadaId, setDestacadaId] = useState(null);
  const destacadaProcesada = useRef(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      setReservas(await listarSolicitudesReserva());
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar las solicitudes."));
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  // Resaltado por ?reserva=ID: muestra la fila aunque un filtro la oculte, una sola vez por enlace.
  useEffect(() => {
    const reservaId = new URLSearchParams(location.search).get("reserva");
    if (!reservaId || cargando || destacadaProcesada.current === reservaId) return;
    if (!reservas.some((reserva) => String(reserva.id) === reservaId)) return;
    destacadaProcesada.current = reservaId;
    setFiltro("todas");
    setBusqueda("");
    setDestacadaId(Number(reservaId));
  }, [location.search, reservas, cargando]);

  useEffect(() => {
    if (destacadaId == null) return;
    document.getElementById(`reserva-${destacadaId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
    const temporizador = window.setTimeout(() => setDestacadaId(null), 5000);
    return () => window.clearTimeout(temporizador);
  }, [destacadaId]);

  const reemplazar = useCallback((actualizada) => {
    setReservas((actuales) => actuales.map((item) => item.id === actualizada.id ? actualizada : item));
  }, []);

  const copiar = useCallback(async (texto, exito) => {
    setMensaje((await copiarTexto(texto)) ? exito : "No se pudo copiar automáticamente. Selecciona el texto y cópialo.");
  }, []);

  function alGarantizar(actualizada) {
    reemplazar(actualizada);
    setReservaAGarantizar(null);
    const pases = actualizada.pases_total;
    const avisoPases = `${pases} ${pases === 1 ? "pase QR emitido" : "pases QR emitidos"}`;
    setMensaje(actualizada.whatsapp_confirmacion_estado === "enviada"
      ? `Reserva garantizada (${avisoPases}). Meta aceptó el WhatsApp; esperamos el reporte de entrega.`
      : `Reserva garantizada (${avisoPases}); el aviso por WhatsApp no se envió. Revisa la plantilla y reintenta.`);
  }

  async function cancelar(reserva) {
    if (reserva.estado === "confirmada") {
      const confirmar = window.confirm(`¿Cancelar la reserva garantizada de ${reserva.nombre_cliente}? Se anularán sus pases QR y no podrán usarse en la puerta.`);
      if (!confirmar) return;
    }
    setActualizandoId(reserva.id);
    setError(null);
    try {
      reemplazar(await actualizarEstadoReserva(reserva.id, "cancelada"));
      setMensaje(`Reserva de ${reserva.nombre_cliente} cancelada.`);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cancelar la reserva."));
    } finally {
      setActualizandoId(null);
    }
  }

  async function reenviarAviso(reserva) {
    setActualizandoId(reserva.id);
    setError(null);
    try {
      const actualizada = await reenviarConfirmacionReserva(reserva.id);
      reemplazar(actualizada);
      setMensaje(actualizada.whatsapp_confirmacion_estado === "enviada" ? "Meta aceptó la confirmación; esperamos el reporte de entrega." : actualizada.whatsapp_confirmacion_error || "No se pudo enviar el aviso.");
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible reenviar la confirmación."));
    } finally {
      setActualizandoId(null);
    }
  }

  async function eliminar(reserva) {
    const confirmar = window.confirm(`¿Eliminar definitivamente la solicitud de ${reserva.nombre_cliente}? Esta acción no se puede deshacer.`);
    if (!confirmar) return;
    setActualizandoId(reserva.id);
    setError(null);
    try {
      await eliminarReservaCancelada(reserva.id);
      setReservas((actuales) => actuales.filter((item) => item.id !== reserva.id));
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible eliminar la solicitud."));
    } finally {
      setActualizandoId(null);
    }
  }

  const resumen = useMemo(() => {
    const garantizadas = reservas.filter((reserva) => reserva.estado === "confirmada");
    return {
      pendientes: reservas.filter((reserva) => reserva.estado === "pendiente").length,
      canceladas: reservas.filter((reserva) => reserva.estado === "cancelada").length,
      garantizadas: garantizadas.length,
      pasesUsados: garantizadas.reduce((suma, reserva) => suma + (reserva.pases_usados ?? 0), 0),
      pasesEmitidos: garantizadas.reduce((suma, reserva) => suma + (reserva.pases_total ?? 0), 0),
    };
  }, [reservas]);

  const conteoPorFiltro = {
    todas: reservas.length,
    pendientes: resumen.pendientes,
    garantizadas: resumen.garantizadas,
    canceladas: resumen.canceladas,
  };

  const visibles = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase("es-CO");
    const digitos = termino.replace(/\D/g, "");
    const estado = ESTADO_POR_FILTRO[filtro];
    return reservas.filter((reserva) => {
      if (estado && reserva.estado !== estado) return false;
      if (!termino) return true;
      if (reserva.nombre_cliente.toLocaleLowerCase("es-CO").includes(termino)) return true;
      return digitos.length > 0 && reserva.telefono.replace(/\D/g, "").includes(digitos);
    });
  }, [reservas, filtro, busqueda]);

  return (
    <div className="reservas-admin-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">ATENCIÓN AL CLIENTE</p>
          <h1>Solicitudes de reserva</h1>
          <p className="page-subtitle">Revisa las solicitudes y garantiza la reserva: se emite un pase QR por asistente.</p>
        </div>
        <Link className="btn btn-outline" to="/reservas" target="_blank" rel="noreferrer">Abrir asistente público ↗</Link>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {mensaje && <div className="reservas-whatsapp-notice" role="status">{mensaje}</div>}

      <div className="reservas-resumen">
        <div className="kpi-card"><div className="kpi-label">Solicitudes recibidas</div><div className="kpi-value">{reservas.length}</div></div>
        <div className="kpi-card"><div className="kpi-label">Pendientes por revisar</div><div className="kpi-value">{resumen.pendientes}</div></div>
        <div className="kpi-card"><div className="kpi-label">Garantizadas</div><div className="kpi-value">{resumen.garantizadas}</div></div>
        <div className="kpi-card"><div className="kpi-label">Pases usados / emitidos</div><div className="kpi-value">{resumen.pasesUsados} / {resumen.pasesEmitidos}</div></div>
      </div>

      <section className="card reservas-admin-card">
        <div className="section-heading"><div><p className="section-kicker">MESAS Y PALCOS</p><h2>Reservas del club</h2></div><button className="btn btn-outline btn-sm" onClick={cargar} disabled={cargando}>Actualizar</button></div>

        <div className="reservas-herramientas">
          <div className="reservas-tabs" role="group" aria-label="Filtrar por estado">
            {FILTROS.map((opcion) => (
              <button key={opcion.clave} type="button" className={`reservas-tab${filtro === opcion.clave ? " activa" : ""}`} aria-pressed={filtro === opcion.clave} onClick={() => setFiltro(opcion.clave)}>
                {opcion.etiqueta} <span className="reservas-tab-conteo">{conteoPorFiltro[opcion.clave]}</span>
              </button>
            ))}
          </div>
          <input className="reservas-busqueda" type="search" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} placeholder="Buscar por nombre o teléfono" aria-label="Buscar reservas por nombre o teléfono" />
        </div>

        {cargando ? <p className="reservas-admin-empty">Cargando solicitudes…</p> : reservas.length === 0 ? (
          <p className="reservas-admin-empty">Todavía no hay solicitudes. Comparte el enlace del asistente para recibir reservas.</p>
        ) : visibles.length === 0 ? (
          <p className="reservas-admin-empty">Ninguna reserva coincide con el filtro o la búsqueda.</p>
        ) : (
          <div className="table-scroll"><table className="data-table reservas-table">
            <thead><tr><th>Cliente</th><th>Evento</th><th>Promotor</th><th>Reserva</th><th>Solicitud</th><th>Estado y garantía</th><th>Pases</th><th>Acción</th></tr></thead>
            <tbody>{visibles.map((reserva) => {
              const ocupada = actualizandoId === reserva.id;
              const garantizada = reserva.estado === "confirmada" && reserva.garantizada;
              const total = reserva.pases_total ?? 0;
              const usados = reserva.pases_usados ?? 0;
              const consumo = reserva.consumo_minimo != null ? pesos(reserva.consumo_minimo) : null;
              return (
                <tr key={reserva.id} id={`reserva-${reserva.id}`} className={destacadaId === reserva.id ? "reserva-destacada" : undefined}>
                  <td><strong>{reserva.nombre_cliente}</strong><a className="reserva-telefono" href={`tel:${reserva.telefono}`}>{reserva.telefono}</a>{reserva.notas && <small className="reserva-nota">{reserva.notas}</small>}</td>
                  <td>{reserva.evento_nombre}</td>
                  <td>{reserva.promotor_nombre ?? (reserva.promotor_id ? `Promotor #${reserva.promotor_id}` : "Directa")}</td>
                  <td>{reserva.tipo === "mesa" ? "Mesa" : "Palco"}<small className="reserva-detalle">{reserva.asistentes} {reserva.asistentes === 1 ? "persona" : "personas"}</small></td>
                  <td>{fechaHora(reserva.fecha_solicitud)}</td>
                  <td>
                    <Badge variante={varianteEstado[reserva.estado] ?? "neutral"}>{garantizada ? "Garantizada" : reserva.estado}</Badge>
                    {garantizada && (
                      <div className="reserva-garantia">
                        {reserva.codigo_garantia && <button type="button" className="reserva-codigo" title="Copiar código de garantía" onClick={() => copiar(reserva.codigo_garantia, "Código de garantía copiado.")}>{reserva.codigo_garantia}</button>}
                        {reserva.ubicacion_asignada && <small>Ubicación: {reserva.ubicacion_asignada}</small>}
                        {reserva.hora_limite && <small>Llegar antes de las {reserva.hora_limite}</small>}
                        {consumo && <small>Consumo mínimo: {consumo}</small>}
                      </div>
                    )}
                    {reserva.estado === "confirmada" && <small className="reserva-whatsapp-estado">WhatsApp: {textoEstadoWhatsApp[reserva.whatsapp_confirmacion_estado] ?? "pendiente"}{reserva.whatsapp_confirmacion_error && <span title={reserva.whatsapp_confirmacion_error}> · {reserva.whatsapp_confirmacion_error}</span>}</small>}
                  </td>
                  <td>
                    {reserva.estado === "confirmada" && total > 0 ? (
                      <div className="reserva-progreso">
                        <span>{usados}/{total}</span>
                        <div className="reserva-progreso-barra" role="progressbar" aria-label="Pases usados" aria-valuemin={0} aria-valuemax={total} aria-valuenow={usados}><span style={{ width: `${Math.min(100, (usados / total) * 100)}%` }} /></div>
                      </div>
                    ) : <span className="reserva-sin-accion">—</span>}
                  </td>
                  <td>
                    <div className="reserva-acciones">
                      {reserva.estado === "pendiente" && <>
                        <button className="btn btn-primary btn-sm" disabled={ocupada} onClick={() => setReservaAGarantizar(reserva)}>Confirmar</button>
                        <button className="btn btn-outline btn-sm" disabled={ocupada} onClick={() => cancelar(reserva)}>Cancelar</button>
                      </>}
                      {reserva.estado === "confirmada" && <>
                        {total > 0 && <button className="btn btn-outline btn-sm" disabled={ocupada} onClick={() => setReservaConPases(reserva)}>Ver pases</button>}
                        {puedeReintentarWhatsApp(reserva.whatsapp_confirmacion_estado) && <button className="btn btn-outline btn-sm" disabled={ocupada} onClick={() => reenviarAviso(reserva)}>Reintentar WhatsApp</button>}
                        <button className="btn btn-outline btn-sm reserva-eliminar" disabled={ocupada} onClick={() => cancelar(reserva)}>{ocupada ? "Cancelando…" : "Cancelar"}</button>
                      </>}
                      {reserva.estado === "cancelada" && <button className="btn btn-outline btn-sm reserva-eliminar" disabled={ocupada} onClick={() => eliminar(reserva)}>{ocupada ? "Eliminando…" : "Eliminar"}</button>}
                    </div>
                  </td>
                </tr>
              );
            })}</tbody>
          </table></div>
        )}
      </section>
      <p className="reservas-admin-nota">Garantiza solo después de validar disponibilidad y contactar al cliente. Una reserva con invitados ya ingresados no se puede cancelar. Las solicitudes canceladas se pueden eliminar definitivamente.</p>

      {reservaAGarantizar && <GarantizarModal reserva={reservaAGarantizar} onClose={() => setReservaAGarantizar(null)} onGarantizada={alGarantizar} />}
      {reservaConPases && <PasesModal reserva={reservaConPases} onClose={() => setReservaConPases(null)} />}
    </div>
  );
}
