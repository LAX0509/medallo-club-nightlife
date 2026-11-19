import { useEffect, useMemo, useState } from "react";
import { QrInvitadoModal } from "../components/QrInvitadoModal";
import { useAuth } from "../store/AuthContext";
import { ROLES } from "../utils/roles";
import { BadgeEstado } from "../components/Badge";
import { AlertBanner } from "../components/AlertBanner";
import { listarEventos } from "../services/eventosService";
import { eventoInicial } from "../utils/eventos";
import { listarUsuarios } from "../services/usuariosService";
import { listarInvitados, obtenerResumenInvitados, registrarInvitado, eliminarInvitado } from "../services/invitadosService";
import { listarComisiones, crearComision, actualizarComision } from "../services/comisionesService";
import { guardarMetaPromotor, obtenerMetaPromotor } from "../services/promotoresService";
import { mensajeDeError } from "../services/apiClient";
import "./ListasComisionesPage.css";

function formatoCOP(valor) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(valor ?? 0);
}

export function ListasComisionesPage({ seccion = "todo" }) {
  const { usuario } = useAuth();
  const esAdmin = usuario.rol === ROLES.ADMINISTRADOR;

  const [eventos, setEventos] = useState([]);
  const [promotores, setPromotores] = useState([]);
  const [eventoId, setEventoId] = useState(null);
  const [promotorFiltro, setPromotorFiltro] = useState("");
  const [busqueda, setBusqueda] = useState("");

  const [invitados, setInvitados] = useState([]);
  const [comisiones, setComisiones] = useState([]);
  const [resumenInvitados, setResumenInvitados] = useState({ total: 0, ingresaron: 0, pendientes: 0 });
  const [error, setError] = useState(null);
  const [metaPromotor, setMetaPromotor] = useState(null);
  const [objetivoMeta, setObjetivoMeta] = useState("");
  const [guardandoMeta, setGuardandoMeta] = useState(false);
  const [importando, setImportando] = useState(false);
  const [resultadoImportacion, setResultadoImportacion] = useState(null);
  const [invitadoQr, setInvitadoQr] = useState(null);

  const [nuevoInvitado, setNuevoInvitado] = useState({ nombre: "", promotorId: "" });
  const [nuevaComision, setNuevaComision] = useState({ promotorId: "", porcentaje: "10" });

  useEffect(() => {
    listarEventos().then((data) => {
      setEventos(data.items);
      if (data.items.length > 0) setEventoId(eventoInicial(data.items).id);
    });
    if (esAdmin) {
      listarUsuarios({ rol: "Promotor" }).then((data) => setPromotores(data.items));
    }
  }, [esAdmin]);

  async function recargar() {
    if (!eventoId) return;
    setError(null);
    try {
      const [invitadosResp, comisionesResp, resumenResp] = await Promise.all([
        listarInvitados({
          eventoId,
          promotorId: esAdmin ? promotorFiltro || undefined : undefined,
          limit: 100,
        }),
        listarComisiones({ eventoId, promotorId: esAdmin ? promotorFiltro || undefined : undefined }),
        obtenerResumenInvitados({ eventoId, promotorId: esAdmin ? promotorFiltro || undefined : undefined }),
      ]);
      setInvitados(invitadosResp.items);
      setComisiones(comisionesResp);
      setResumenInvitados(resumenResp);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar la información"));
    }
  }

  useEffect(() => {
    recargar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventoId, promotorFiltro]);

  useEffect(() => {
    if (esAdmin || !eventoId) return;
    obtenerMetaPromotor(eventoId)
      .then((respuesta) => {
        setMetaPromotor(respuesta.objetivo);
        setObjetivoMeta(respuesta.objetivo ? String(respuesta.objetivo) : "");
      })
      .catch((err) => setError(mensajeDeError(err, "No fue posible cargar tu meta.")));
  }, [esAdmin, eventoId]);

  const invitadosFiltrados = useMemo(
    () =>
      invitados.filter((i) => i.nombre.toLowerCase().includes(busqueda.toLowerCase())),
    [invitados, busqueda]
  );
  const mostrarResumen = seccion === "todo" || seccion === "resumen";
  const mostrarInvitados = seccion === "todo" || seccion === "invitados";
  const mostrarComisiones = seccion === "todo" || seccion === "comisiones";
  const tituloPagina = {
    todo: "Listas y comisiones",
    resumen: "Resumen del promotor",
    invitados: "Mis invitados",
    comisiones: "Mis comisiones",
  }[seccion] ?? "Mi operación";
  const subtituloPagina = {
    todo: "Organiza asistentes y consulta el rendimiento del equipo.",
    resumen: "Revisa tu avance y el resultado de tus invitados en el evento.",
    invitados: "Administra tu lista y registra nuevos asistentes.",
    comisiones: "Consulta los pagos asociados a tu actividad como promotor.",
  }[seccion] ?? "";
  const comisionPendiente = comisiones.filter((comision) => comision.estado === "pendiente").reduce((total, comision) => total + Number(comision.monto), 0);
  const comisionLiquidada = comisiones.filter((comision) => comision.estado === "liquidada").reduce((total, comision) => total + Number(comision.monto), 0);

  async function handleAgregarInvitado(event) {
    event.preventDefault();
    setError(null);
    try {
      await registrarInvitado({
        nombre: nuevoInvitado.nombre,
        evento_id: eventoId,
        promotor_id: esAdmin ? Number(nuevoInvitado.promotorId) : usuario.id,
      });
      setNuevoInvitado({ nombre: "", promotorId: "" });
      recargar();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible registrar el invitado"));
    }
  }

  async function handleEliminarInvitado(id) {
    await eliminarInvitado(id);
    recargar();
  }

  async function handleImportarCSV(event) {
    const archivo = event.target.files?.[0];
    event.target.value = "";
    if (!archivo || !eventoId) return;
    setImportando(true);
    setError(null);
    setResultadoImportacion(null);
    try {
      const lineas = (await archivo.text()).replace(/^\uFEFF/, "").split(/\r?\n/).map((linea) => linea.trim()).filter(Boolean);
      const nombres = lineas.map((linea) => {
        const primeraColumna = linea.match(/^\s*"((?:[^"]|"")*)"\s*(?:,|$)/)?.[1]
          ?? linea.split(",")[0];
        return primeraColumna.replace(/^"|"$/g, "").replace(/""/g, '"').trim();
      }).filter((nombre) => nombre && !/^nombre(?:\s+del\s+invitado)?$/i.test(nombre));
      if (!nombres.length) throw new Error("El CSV no contiene nombres para importar.");
      if (nombres.length > 100) throw new Error("Importa máximo 100 invitados por archivo.");

      let importados = 0;
      const fallidos = [];
      for (const nombre of nombres) {
        try {
          await registrarInvitado({
            nombre,
            evento_id: eventoId,
            promotor_id: esAdmin ? Number(nuevoInvitado.promotorId) : usuario.id,
          });
          importados += 1;
        } catch {
          fallidos.push(nombre);
        }
      }
      setResultadoImportacion({ importados, fallidos });
      await recargar();
    } catch (err) {
      setError(err.message || mensajeDeError(err, "No fue posible importar el archivo."));
    } finally {
      setImportando(false);
    }
  }

  async function handleGuardarMeta(event) {
    event.preventDefault();
    const objetivo = Number(objetivoMeta);
    if (!Number.isInteger(objetivo) || objetivo < 1 || objetivo > 10000) {
      setError("Tu meta debe ser un número entre 1 y 10.000.");
      return;
    }
    setGuardandoMeta(true);
    setError(null);
    try {
      const respuesta = await guardarMetaPromotor(eventoId, objetivo);
      setMetaPromotor(respuesta.objetivo);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible guardar tu meta."));
    } finally {
      setGuardandoMeta(false);
    }
  }

  function descargarComisiones() {
    const filas = [["Evento", "Promotor", "Porcentaje", "Monto COP", "Estado"]];
    for (const comision of comisiones) {
      filas.push([
        eventos.find((evento) => evento.id === comision.evento_id)?.nombre ?? `Evento ${comision.evento_id}`,
        esAdmin ? promotores.find((p) => p.id === comision.promotor_id)?.nombre ?? `#${comision.promotor_id}` : usuario.nombre,
        `${comision.porcentaje}%`,
        comision.monto,
        comision.estado,
      ]);
    }
    const csv = `\uFEFF${filas.map((fila) => fila.map((valor) => `"${String(valor ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n")}`;
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    enlace.download = `comisiones-evento-${eventoId}.csv`;
    enlace.click();
    window.setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
  }

  async function handleCrearComision(event) {
    event.preventDefault();
    setError(null);
    try {
      await crearComision({
        promotor_id: Number(nuevaComision.promotorId),
        evento_id: eventoId,
        porcentaje: nuevaComision.porcentaje,
      });
      setNuevaComision({ promotorId: "", porcentaje: "10" });
      recargar();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible crear la comisión"));
    }
  }

  async function handleLiquidarComision(comision) {
    await actualizarComision(comision.id, { estado: "liquidada", monto: comision.monto });
    recargar();
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">GESTIÓN DE INVITADOS</p>
          <h1>{tituloPagina}</h1>
          <p className="page-subtitle">{subtituloPagina}</p>
        </div>
        <select
          value={eventoId ?? ""}
          onChange={(e) => setEventoId(Number(e.target.value))}
          className="event-select"
        >
          {eventos.map((evento) => (
            <option key={evento.id} value={evento.id}>
              {evento.nombre} — {evento.fecha}
            </option>
          ))}
        </select>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}

      {mostrarResumen && <div className="promotor-resumen-grid">
        <article className="card promotor-resumen-card"><span>Invitados en la lista</span><strong>{resumenInvitados.total}</strong></article>
        <article className="card promotor-resumen-card"><span>Ingresaron al evento</span><strong>{resumenInvitados.ingresaron}</strong></article>
        <article className="card promotor-resumen-card"><span>Pendientes de ingreso</span><strong>{resumenInvitados.pendientes}</strong></article>
        <article className="card promotor-resumen-card"><span>Comisión pendiente</span><strong>{formatoCOP(comisionPendiente)}</strong></article>
        <article className="card promotor-resumen-card"><span>Comisión pagada</span><strong>{formatoCOP(comisionLiquidada)}</strong></article>
      </div>}

      {mostrarResumen && !esAdmin && eventoId && (
        <section className="card promotor-meta-card">
          <div><p className="section-kicker">OBJETIVO PERSONAL</p><h2>Tu meta para este evento</h2><p>{metaPromotor ? `${Math.min(100, Math.round((resumenInvitados.total / metaPromotor) * 100))}% completado · ${resumenInvitados.total} de ${metaPromotor} invitados` : "Define una meta de invitados para esta fecha."}</p></div>
          <form onSubmit={handleGuardarMeta}><input type="number" min="1" max="10000" required aria-label="Meta de invitados" placeholder="Ej. 30" value={objetivoMeta} onChange={(event) => setObjetivoMeta(event.target.value)} /><button className="btn btn-primary" disabled={guardandoMeta}>{guardandoMeta ? "Guardando…" : "Guardar meta"}</button></form>
          {metaPromotor && <div className="promotor-meta-barra" role="progressbar" aria-valuenow={Math.min(100, Math.round((resumenInvitados.total / metaPromotor) * 100))} aria-valuemin="0" aria-valuemax="100"><span style={{ width: `${Math.min(100, Math.round((resumenInvitados.total / metaPromotor) * 100))}%` }} /></div>}
        </section>
      )}

      <div className={`listas-grid listas-seccion-${seccion}`}>
        {mostrarInvitados && <div className="card">
          <div className="section-heading"><div><p className="section-kicker">LISTA DEL EVENTO</p><h2>Invitados</h2></div><span className="table-count">{invitadosFiltrados.length}</span></div>
          <div className="filtros-fila">
            <input
              placeholder="Buscar invitado..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
            {esAdmin && (
              <select value={promotorFiltro} onChange={(e) => setPromotorFiltro(e.target.value)}>
                <option value="">Todos los promotores</option>
                {promotores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="table-scroll"><table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>QR</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {invitadosFiltrados.map((invitado) => (
                <tr key={invitado.id}>
                  <td>{invitado.nombre}</td>
                  <td className="qr-code-cell">{invitado.qr_code}</td>
                  <td>
                    <BadgeEstado estado={invitado.estado} />
                  </td>
                  <td>
                    <div className="invitado-acciones">
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => setInvitadoQr(invitado)}>Ver QR</button>
                      <button className="btn btn-outline btn-sm" type="button" onClick={() => handleEliminarInvitado(invitado.id)}>Quitar</button>
                    </div>
                  </td>
                </tr>
              ))}
              {invitadosFiltrados.length === 0 && (
                <tr>
                  <td colSpan={4} className="empty-state">
                    Sin invitados registrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table></div>

          <form className="inline-form" onSubmit={handleAgregarInvitado}>
            <input
              placeholder="Nombre del invitado"
              required
              value={nuevoInvitado.nombre}
              onChange={(e) => setNuevoInvitado((v) => ({ ...v, nombre: e.target.value }))}
            />
            {esAdmin && (
              <select
                required
                value={nuevoInvitado.promotorId}
                onChange={(e) => setNuevoInvitado((v) => ({ ...v, promotorId: e.target.value }))}
              >
                <option value="" disabled>
                  Promotor
                </option>
                {promotores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            )}
            <button className="btn btn-primary" type="submit">
              Agregar invitado
            </button>
          </form>
          <div className="listas-importar"><label className="btn btn-outline" htmlFor="importar-invitados-csv">{importando ? "Importando…" : "Importar CSV"}</label><input id="importar-invitados-csv" type="file" accept=".csv,text/csv" onChange={handleImportarCSV} disabled={importando || (esAdmin && !nuevoInvitado.promotorId)} /><small>CSV de una columna llamada “Nombre”, máximo 100 invitados. {esAdmin && !nuevoInvitado.promotorId && "Selecciona primero el promotor arriba."}</small></div>
          {resultadoImportacion && <p className="listas-importar-resultado">{resultadoImportacion.importados} invitados importados{resultadoImportacion.fallidos.length ? `; ${resultadoImportacion.fallidos.length} no se pudieron agregar (${resultadoImportacion.fallidos.slice(0, 3).join(", ")}${resultadoImportacion.fallidos.length > 3 ? "…" : ""}).` : "."}</p>}
        </div>}

        {mostrarComisiones && <div className="card">
          <div className="section-heading"><div><p className="section-kicker">PAGOS Y RENDIMIENTO</p><h2>Comisiones</h2></div><div className="comisiones-encabezado"><span className="table-count">{comisiones.length}</span><button className="btn btn-outline btn-sm" type="button" onClick={descargarComisiones} disabled={!comisiones.length}>Descargar CSV</button></div></div>
          <div className="table-scroll"><table className="data-table">
            <thead>
              <tr>
                <th>Promotor</th>
                <th>%</th>
                <th>Monto</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {comisiones.map((comision) => (
                <tr key={comision.id}>
                  <td>
                    {esAdmin
                      ? promotores.find((p) => p.id === comision.promotor_id)?.nombre ??
                        `#${comision.promotor_id}`
                      : usuario.nombre}
                  </td>
                  <td>{comision.porcentaje}%</td>
                  <td>{formatoCOP(comision.monto)}</td>
                  <td>
                    <BadgeEstado estado={comision.estado} />
                  </td>
                  <td>
                    {esAdmin && comision.estado === "pendiente" && (
                      <button
                        className="btn btn-outline btn-sm"
                        onClick={() => handleLiquidarComision(comision)}
                      >
                        Liquidar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {comisiones.length === 0 && (
                <tr>
                  <td colSpan={5} className="empty-state">
                    Sin comisiones registradas.
                  </td>
                </tr>
              )}
            </tbody>
          </table></div>

          {esAdmin && (
            <form className="inline-form" onSubmit={handleCrearComision}>
              <select
                required
                value={nuevaComision.promotorId}
                onChange={(e) => setNuevaComision((v) => ({ ...v, promotorId: e.target.value }))}
              >
                <option value="" disabled>
                  Promotor
                </option>
                {promotores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nombre}
                  </option>
                ))}
              </select>
              <input
                type="number"
                min="0"
                max="100"
                step="0.5"
                value={nuevaComision.porcentaje}
                onChange={(e) => setNuevaComision((v) => ({ ...v, porcentaje: e.target.value }))}
              />
              <button className="btn btn-primary" type="submit">
                Asignar comisión
              </button>
            </form>
          )}
        </div>}
      </div>
      {invitadoQr && <QrInvitadoModal invitado={invitadoQr} onClose={() => setInvitadoQr(null)} />}
    </div>
  );
}
