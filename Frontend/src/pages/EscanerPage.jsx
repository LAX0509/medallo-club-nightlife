import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { QrCameraScanner } from "../components/QrCameraScanner";
import { Badge, BadgeResultado, BadgeNivel } from "../components/Badge";
import { AlertBanner } from "../components/AlertBanner";
import { listarEventos } from "../services/eventosService";
import { eventoInicial } from "../utils/eventos";
import { listarInvitados } from "../services/invitadosService";
import {
  listarAccesos,
  listarIncidenciasPuerta,
  obtenerResumenPuerta,
  registrarAccesoQR,
  registrarCortesiaManual,
  registrarIncidenciaPuerta,
} from "../services/accesosService";
import { mensajeDeError } from "../services/apiClient";
import { detectarFormatoQr, ETIQUETA_FORMATO, FORMATOS_QR } from "../utils/qrCode";
import "./EscanerPage.css";

const TEXTO_TIPO_INCIDENCIA = {
  qr_duplicado: "QR ya utilizado",
  qr_rechazado: "QR no válido",
  nombre_diferente: "Nombre diferente",
  otra: "Otra incidencia",
};

function fechaHora(fecha) {
  return fecha
    ? new Date(fecha).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" })
    : "—";
}

export function EscanerPage({ vista = "escaner" }) {
  const [eventos, setEventos] = useState([]);
  const [eventoId, setEventoId] = useState(null);
  const [camaraActiva, setCamaraActiva] = useState(true);
  const [ultimoResultado, setUltimoResultado] = useState(null);
  const [qrManual, setQrManual] = useState("");
  const [formatoLeido, setFormatoLeido] = useState(null);
  const [busqueda, setBusqueda] = useState("");
  const [invitados, setInvitados] = useState([]);
  const [accesos, setAccesos] = useState([]);
  const [incidencias, setIncidencias] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState(null);
  const [mostrarCortesia, setMostrarCortesia] = useState(false);
  const [mostrarFormularioIncidencia, setMostrarFormularioIncidencia] = useState(false);
  const [cortesia, setCortesia] = useState({ nombre: "", justificacion: "" });
  const [incidencia, setIncidencia] = useState({ tipo: "nombre_diferente", persona: "", descripcion: "" });
  const [enviando, setEnviando] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [guardandoIncidencia, setGuardandoIncidencia] = useState(false);

  useEffect(() => {
    listarEventos()
      .then((data) => {
        const abiertos = data.items.filter((evento) => evento.estado !== "cerrado");
        const opciones = abiertos.length ? abiertos : data.items;
        setEventos(opciones);
        if (opciones.length) setEventoId(eventoInicial(opciones).id);
      })
      .catch((err) => setError(mensajeDeError(err, "No fue posible cargar los eventos.")))
      .finally(() => setCargando(false));
  }, []);

  const recargarDatosEvento = useCallback(async () => {
    if (!eventoId) return;
    try {
      const [resumenResp, accesosResp, invitadosResp, incidenciasResp] = await Promise.all([
        obtenerResumenPuerta(eventoId),
        listarAccesos({ eventoId, limit: 50 }),
        listarInvitados({ eventoId, limit: 100 }),
        listarIncidenciasPuerta({ eventoId, limit: 50 }),
      ]);
      setResumen(resumenResp);
      setAccesos(accesosResp.items);
      setInvitados(invitadosResp.items);
      setIncidencias(incidenciasResp);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar el resumen del evento."));
    }
  }, [eventoId]);

  useEffect(() => {
    recargarDatosEvento();
  }, [recargarDatosEvento]);

  useEffect(() => {
    setCamaraActiva(vista === "escaner");
    setUltimoResultado(null);
    setFormatoLeido(null);
    setError(null);
  }, [vista, eventoId]);

  const manejarErrorCamara = useCallback(() => {
    setError("No se pudo acceder a la cámara. Usa el registro manual o busca al invitado.");
  }, []);

  const procesarResultado = useCallback(async (qrCode) => {
    if (!eventoId || enviando) return;
    let formato;
    try { formato = detectarFormatoQr(qrCode).formato; }
    catch { setFormatoLeido(null); setError("Ese QR no es un pase de Medallo Club. Pide al cliente su pase o busca al invitado por nombre."); return; }
    setEnviando(true);
    setCamaraActiva(false);
    setError(null);
    setFormatoLeido(formato);
    try {
      // El backend también normaliza: se envía el texto tal cual lo leyó la cámara.
      const data = await registrarAccesoQR({ eventoId, qrCode });
      setUltimoResultado(data);
      await recargarDatosEvento();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible registrar el acceso."));
    } finally {
      setEnviando(false);
    }
  }, [eventoId, enviando, recargarDatosEvento]);

  async function enviarCortesia(event) {
    event.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const data = await registrarCortesiaManual({
        eventoId,
        nombreCortesia: cortesia.nombre,
        justificacion: cortesia.justificacion,
      });
      setUltimoResultado(data);
      setMostrarCortesia(false);
      setCortesia({ nombre: "", justificacion: "" });
      await recargarDatosEvento();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible registrar la cortesía."));
    } finally {
      setEnviando(false);
    }
  }

  async function enviarIncidencia(event) {
    event.preventDefault();
    if (!eventoId) return;
    setGuardandoIncidencia(true);
    setError(null);
    try {
      await registrarIncidenciaPuerta({
        evento_id: eventoId,
        tipo: incidencia.tipo,
        persona: incidencia.persona.trim() || null,
        descripcion: incidencia.descripcion.trim(),
      });
      setIncidencia({ tipo: "nombre_diferente", persona: "", descripcion: "" });
      setMostrarFormularioIncidencia(false);
      await recargarDatosEvento();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible guardar la incidencia."));
    } finally {
      setGuardandoIncidencia(false);
    }
  }

  async function permitirIngreso(invitado) {
    await procesarResultado(invitado.qr_code);
    setBusqueda("");
  }

  const eventoSeleccionado = eventos.find((evento) => evento.id === eventoId);
  const invitadosFiltrados = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase("es-CO");
    if (!termino) return [];
    return invitados.filter((invitado) =>
      `${invitado.nombre} ${invitado.qr_code}`.toLocaleLowerCase("es-CO").includes(termino)
    ).slice(0, 12);
  }, [busqueda, invitados]);
  const nombresInvitados = useMemo(
    () => new Map(invitados.map((invitado) => [invitado.id, invitado.nombre])),
    [invitados]
  );
  const accesosFallidos = accesos.filter((acceso) => acceso.resultado !== "valido");
  const titulo = {
    escaner: "Escáner QR",
    buscar: "Buscar invitado",
    historial: "Historial e incidencias",
  }[vista] ?? "Control de acceso";

  return (
    <div className="puerta-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">OPERACIÓN DE PUERTA</p>
          <h1>{titulo}</h1>
          <p className="page-subtitle">Valida entradas y consulta el movimiento del evento.</p>
        </div>
        <label className="puerta-evento-selector"><span>Evento activo</span><select value={eventoId ?? ""} onChange={(event) => setEventoId(Number(event.target.value))} className="event-select" disabled={!eventos.length}>
          {eventos.map((evento) => <option key={evento.id} value={evento.id}>{evento.nombre} — {evento.fecha}</option>)}
        </select></label>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {!cargando && eventos.length === 0 && <section className="card puerta-sin-evento"><strong>No hay eventos para validar</strong><p>Cuando administración publique un evento, podrás seleccionarlo aquí.</p></section>}

      {eventoId && <>
        <section className="puerta-aforo-grid" aria-label="Estado del aforo">
          <article className="card puerta-aforo-card puerta-aforo-principal"><span>Personas dentro</span><strong>{resumen?.accesos_validos ?? "—"}<small> / {resumen?.aforo_maximo ?? "—"}</small></strong><div className="puerta-aforo-barra"><span style={{ width: `${Math.min(100, (resumen?.porcentaje_aforo ?? 0) * 100)}%` }} /></div><small>{resumen ? `${Math.round(resumen.porcentaje_aforo * 100)}% del aforo` : "Cargando aforo…"}</small></article>
          <article className="card puerta-aforo-card"><span>Ingresos válidos</span><strong>{resumen?.accesos_validos ?? "—"}</strong></article>
          <article className="card puerta-aforo-card"><span>QR duplicados</span><strong>{resumen?.accesos_duplicados ?? "—"}</strong></article>
          <article className="card puerta-aforo-card"><span>Rechazados</span><strong>{resumen?.accesos_rechazados ?? "—"}</strong></article>
        </section>

        {vista === "escaner" && <div className="escaner-grid puerta-contenido-grid">
          <section className="card scan-card">
            <div className="section-heading"><div><p className="section-kicker">LECTOR QR</p><h2>Escanear entrada</h2></div><span className="camera-status"><span className={`status-dot${camaraActiva ? "" : " puerta-dot-pausa"}`} />{camaraActiva ? "Cámara activa" : "En pausa"}</span></div>
            {camaraActiva ? <QrCameraScanner activo={camaraActiva} onLectura={procesarResultado} onError={manejarErrorCamara} /> : <div className={`qr-camera-paused${ultimoResultado ? " puerta-resultado-pausa" : ""}`}>
              {ultimoResultado ? <><strong className={`puerta-resultado puerta-resultado-${ultimoResultado.acceso.resultado}`}>{ultimoResultado.acceso.resultado === "valido" ? "INGRESO PERMITIDO" : ultimoResultado.acceso.resultado === "duplicado" ? "QR YA UTILIZADO" : "INGRESO RECHAZADO"}</strong><p>{nombresInvitados.get(ultimoResultado.acceso.invitado_id) ?? (ultimoResultado.acceso.invitado_id ? `Invitado #${ultimoResultado.acceso.invitado_id}` : "No se encontró un invitado asociado.")}</p><BadgeResultado resultado={ultimoResultado.acceso.resultado} />{formatoLeido && <span className="qr-formato-chip">Leído como: {ETIQUETA_FORMATO[formatoLeido] ?? formatoLeido}</span>}{ultimoResultado.alertas_generadas?.map((alerta) => <div key={alerta.id} className={`alert-banner nivel-${alerta.nivel}`}><BadgeNivel nivel={alerta.nivel} /><span>{alerta.descripcion}</span></div>)}</> : <p>Cámara en pausa</p>}
              <button className="btn btn-primary" onClick={() => { setUltimoResultado(null); setFormatoLeido(null); setCamaraActiva(true); }}>Escanear siguiente</button>
            </div>}
            <form className="form-field scan-manual" onSubmit={(event) => { event.preventDefault(); if (qrManual.trim()) { procesarResultado(qrManual.trim()); setQrManual(""); } }}>
              <label htmlFor="qr-manual">¿No funciona la cámara? Ingresa el código</label><div className="scan-manual-row"><input id="qr-manual" value={qrManual} onChange={(event) => setQrManual(event.target.value)} placeholder="NLD-…" /><button className="btn btn-outline" type="submit" disabled={!qrManual.trim() || enviando}>Validar código</button></div>
            </form>
            <details className="qr-formatos-ayuda">
              <summary>Formatos de QR aceptados</summary>
              <ul>{FORMATOS_QR.map((item) => <li key={item.formato}><strong>{item.etiqueta}</strong><span>{item.descripcion}</span></li>)}</ul>
              <p>También se reconoce un texto compartido que incluya el código del pase.</p>
            </details>
            <button className="btn btn-outline btn-block" style={{ marginTop: 12 }} onClick={() => setMostrarCortesia((visible) => !visible)}>Registrar cortesía manual</button>
            {mostrarCortesia && <form className="cortesia-form" onSubmit={enviarCortesia}><div className="form-field"><label htmlFor="cortesia-nombre">Nombre del invitado</label><input id="cortesia-nombre" required value={cortesia.nombre} onChange={(event) => setCortesia((actual) => ({ ...actual, nombre: event.target.value }))} /></div><div className="form-field"><label htmlFor="cortesia-justificacion">Justificación</label><textarea id="cortesia-justificacion" required rows={3} value={cortesia.justificacion} onChange={(event) => setCortesia((actual) => ({ ...actual, justificacion: event.target.value }))} /></div><button className="btn btn-primary btn-block" type="submit" disabled={enviando}>Confirmar cortesía</button></form>}
          </section>
          <aside className="card puerta-ayuda-card"><p className="section-kicker">ACCESO RÁPIDO</p><h2>{eventoSeleccionado?.nombre ?? "Evento"}</h2><p>Busca una invitación por nombre o código si el cliente no puede mostrar su QR.</p><Link className="btn btn-outline btn-block" to="/escaner/buscar">Buscar invitado</Link><div className="puerta-turno-mini"><span>Último resultado</span>{ultimoResultado ? <BadgeResultado resultado={ultimoResultado.acceso.resultado} /> : <strong>Esperando escaneo</strong>}</div><Link className="puerta-historial-link" to="/escaner/historial">Ver historial e incidencias →</Link></aside>
        </div>}

        {vista === "buscar" && <section className="card puerta-busqueda-card"><div className="section-heading"><div><p className="section-kicker">VALIDACIÓN MANUAL</p><h2>Encuentra al invitado</h2></div><span className="table-count">{invitados.length}</span></div><p className="puerta-ayuda">Busca por nombre o pega el código QR. Antes de permitir el ingreso, confirma visualmente que el nombre corresponda a la persona.</p><input className="puerta-busqueda-input" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} placeholder="Nombre o código NLD-…" autoFocus />
          {!busqueda.trim() ? <p className="empty-state">Escribe el nombre o el código para buscar en la lista del evento.</p> : invitadosFiltrados.length === 0 ? <p className="empty-state">No encontramos coincidencias en la lista cargada.</p> : <div className="table-scroll"><table className="data-table"><thead><tr><th>Invitado</th><th>Código</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{invitadosFiltrados.map((invitado) => <tr key={invitado.id}><td><strong>{invitado.nombre}</strong></td><td className="qr-code-cell">{invitado.qr_code}</td><td><Badge>{invitado.estado === "usado" ? "Ingresó" : "Pendiente"}</Badge></td><td><button className="btn btn-primary btn-sm" disabled={invitado.estado === "usado" || enviando} onClick={() => permitirIngreso(invitado)}>{invitado.estado === "usado" ? "Ya ingresó" : "Validar ingreso"}</button></td></tr>)}</tbody></table></div>}
        </section>}

        {vista === "historial" && <div className="puerta-historial-grid">
          <section className="card"><div className="section-heading"><div><p className="section-kicker">MOVIMIENTO RECIENTE</p><h2>Últimos accesos</h2></div><button type="button" className="btn btn-outline btn-sm" onClick={recargarDatosEvento}>Actualizar</button></div>{accesos.length === 0 ? <p className="empty-state">Todavía no hay accesos registrados en este evento.</p> : <div className="table-scroll"><table className="data-table puerta-historial-tabla"><thead><tr><th>Persona</th><th>Resultado</th><th>Hora</th></tr></thead><tbody>{accesos.map((acceso) => <tr key={acceso.id}><td>{nombresInvitados.get(acceso.invitado_id) ?? (acceso.tipo === "cortesia_manual" ? "Cortesía manual" : "Invitado sin identificar")}</td><td><BadgeResultado resultado={acceso.resultado} /></td><td>{fechaHora(acceso.fecha_hora)}</td></tr>)}</tbody></table></div>}</section>
          <section className="card"><div className="section-heading"><div><p className="section-kicker">NOVEDADES DEL TURNO</p><h2>Incidencias</h2></div><span className="table-count">{incidencias.length + accesosFallidos.length}</span></div><p className="puerta-ayuda">Los QR duplicados y rechazados quedan en el historial automáticamente. Aquí puedes documentar diferencias de nombre u otros casos.</p><button className="btn btn-outline btn-block" type="button" onClick={() => setMostrarFormularioIncidencia((visible) => !visible)}>{mostrarFormularioIncidencia ? "Cerrar formulario" : "Registrar incidencia"}</button>
            {mostrarFormularioIncidencia && <form className="puerta-incidencia-form" onSubmit={enviarIncidencia}><div className="form-field"><label htmlFor="incidencia-tipo">Tipo</label><select id="incidencia-tipo" value={incidencia.tipo} onChange={(event) => setIncidencia((actual) => ({ ...actual, tipo: event.target.value }))}><option value="qr_duplicado">QR ya utilizado</option><option value="qr_rechazado">QR no válido</option><option value="nombre_diferente">Nombre diferente</option><option value="otra">Otra incidencia</option></select></div><div className="form-field"><label htmlFor="incidencia-persona">Nombre (opcional)</label><input id="incidencia-persona" maxLength={100} value={incidencia.persona} onChange={(event) => setIncidencia((actual) => ({ ...actual, persona: event.target.value }))} /></div><div className="form-field"><label htmlFor="incidencia-descripcion">Detalle</label><textarea id="incidencia-descripcion" required minLength={3} maxLength={500} rows={3} value={incidencia.descripcion} onChange={(event) => setIncidencia((actual) => ({ ...actual, descripcion: event.target.value }))} placeholder="Describe brevemente lo ocurrido" /></div><button className="btn btn-primary btn-block" type="submit" disabled={guardandoIncidencia}>{guardandoIncidencia ? "Guardando…" : "Guardar incidencia"}</button></form>}
            <div className="puerta-incidencias-lista">{accesosFallidos.slice(0, 5).map((acceso) => <article className="puerta-incidencia-item" key={`acceso-${acceso.id}`}><BadgeResultado resultado={acceso.resultado} /><span>{nombresInvitados.get(acceso.invitado_id) ?? "QR sin invitado válido"}</span><time>{fechaHora(acceso.fecha_hora)}</time></article>)}{incidencias.slice(0, 10).map((item) => <article className="puerta-incidencia-item" key={`incidencia-${item.id}`}><Badge variante="accent">{TEXTO_TIPO_INCIDENCIA[item.tipo] ?? item.tipo}</Badge><span>{item.persona ? `${item.persona}: ` : ""}{item.descripcion}</span><time>{fechaHora(item.fecha_hora)}</time></article>)}{accesosFallidos.length === 0 && incidencias.length === 0 && <p className="empty-state">No hay incidencias registradas.</p>}</div>
          </section>
        </div>}
      </>}
    </div>
  );
}
