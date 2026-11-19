import { useEffect, useId, useRef, useState } from "react";
import { KpiCard } from "../components/KpiCard";
import { AlertBanner } from "../components/AlertBanner";
import { Badge, BadgeNivel } from "../components/Badge";
import { listarEventos } from "../services/eventosService";
import { eventoInicial } from "../utils/eventos";
import { generarInformeJornada, obtenerResumenEvento } from "../services/dashboardService";
import { actualizarAlerta } from "../services/alertasService";
import { mensajeDeError } from "../services/apiClient";
import "./DashboardPage.css";

function formatoCOP(valor) {
  return new Intl.NumberFormat("es-CO", {
    style: "currency",
    currency: "COP",
    maximumFractionDigits: 0,
  }).format(valor ?? 0);
}

function porcentajeAforo(fraccion) {
  return `${Math.round((fraccion ?? 0) * 100)}%`;
}

function ListaCritica({ titulo, items }) {
  return (
    <p className="informe-lista-critica">
      <strong>{titulo}:</strong> {items.length > 0 ? items.join(", ") : "ninguno"}
    </p>
  );
}

function InformeJornada({ eventoId }) {
  const idIa = useId();
  const raiz = useRef(null);
  const solicitud = useRef(0);
  const [usarIa, setUsarIa] = useState(true);
  const [informe, setInforme] = useState(null);
  const [generando, setGenerando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const contador = solicitud;
    return () => { contador.current += 1; };
  }, []);

  async function generar() {
    solicitud.current += 1;
    const numero = solicitud.current;
    setGenerando(true);
    setError(null);
    try {
      const datos = await generarInformeJornada(eventoId, usarIa);
      if (solicitud.current === numero) setInforme(datos);
    } catch (err) {
      if (solicitud.current === numero) setError(mensajeDeError(err, "No fue posible generar el informe de la jornada."));
    } finally {
      if (solicitud.current === numero) setGenerando(false);
    }
  }

  function imprimir() {
    const ocultos = [];
    let nodo = raiz.current;
    while (nodo && nodo !== document.body && nodo.parentElement) {
      Array.from(nodo.parentElement.children).forEach((hermano) => {
        if (hermano !== nodo) {
          hermano.setAttribute("data-no-imprimir", "");
          ocultos.push(hermano);
        }
      });
      nodo = nodo.parentElement;
    }
    window.addEventListener(
      "afterprint",
      () => ocultos.forEach((el) => el.removeAttribute("data-no-imprimir")),
      { once: true },
    );
    window.print();
  }

  const narrativa = informe?.narrativa;
  const origenIa = Boolean(narrativa?.generado_con?.startsWith("IA"));

  return (
    <section className="card informe-jornada" ref={raiz} aria-labelledby="informe-titulo">
      <div className="section-heading informe-controles">
        <div>
          <p className="section-kicker">CIERRE</p>
          <h2 id="informe-titulo">Informe de la jornada</h2>
        </div>
        <div className="informe-acciones">
          <label className="informe-casilla" htmlFor={idIa}>
            <input id={idIa} type="checkbox" checked={usarIa} onChange={(e) => setUsarIa(e.target.checked)} />
            Redactar con IA
          </label>
          <button type="button" className="btn btn-primary btn-sm" onClick={generar} disabled={generando}>
            {generando ? "Generando…" : informe ? "Volver a generar" : "Generar informe"}
          </button>
          {informe && (
            <button type="button" className="btn btn-outline btn-sm" onClick={imprimir}>
              Imprimir informe
            </button>
          )}
        </div>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {generando && !informe && <p className="informe-estado" role="status">Armando el informe con las cifras reales del evento…</p>}
      {!informe && !generando && !error && (
        <p className="informe-estado">
          Genera un resumen de cierre con puerta, reservas, inventario y comisiones, más recomendaciones para la próxima fecha.
        </p>
      )}

      {informe && (
        <div className="informe-contenido" aria-busy={generando}>
          <header className="informe-encabezado">
            <h3>{informe.evento.nombre}</h3>
            <p>
              {informe.evento.fecha} · aforo {informe.evento.aforo_maximo} · estado {informe.evento.estado}
            </p>
          </header>

          <div className="informe-narrativa">
            <div className="informe-narrativa-cabecera">
              <strong>Lectura de la jornada</strong>
              <Badge variante={origenIa ? "accent" : "neutral"}>{origenIa ? narrativa.generado_con : "Reglas"}</Badge>
            </div>
            <p>{narrativa.resumen}</p>
            {narrativa.aviso_ia && <small className="informe-aviso">Nota sobre la IA: {narrativa.aviso_ia}</small>}
          </div>

          {narrativa.recomendaciones.length > 0 && (
            <div className="informe-recomendaciones">
              <h3>Recomendaciones</h3>
              <ol>
                {narrativa.recomendaciones.map((r, i) => <li key={i}>{r}</li>)}
              </ol>
            </div>
          )}

          <div className="informe-bloques">
            <div className="informe-bloque">
              <h3>Puerta</h3>
              <dl>
                <div><dt>Ingresos válidos</dt><dd>{informe.puerta.validos}</dd></div>
                <div><dt>Del aforo</dt><dd>{porcentajeAforo(informe.puerta.porcentaje_aforo)}</dd></div>
                <div><dt>Duplicados</dt><dd>{informe.puerta.duplicados}</dd></div>
                <div><dt>Rechazados</dt><dd>{informe.puerta.rechazados}</dd></div>
                <div><dt>Cortesías manuales</dt><dd>{informe.puerta.cortesias_manuales}</dd></div>
              </dl>
            </div>
            <div className="informe-bloque">
              <h3>Reservas</h3>
              <dl>
                <div><dt>Solicitudes</dt><dd>{informe.reservas.solicitudes}</dd></div>
                <div><dt>Garantizadas</dt><dd>{informe.reservas.garantizadas}</dd></div>
                <div><dt>Pendientes</dt><dd>{informe.reservas.pendientes}</dd></div>
                <div><dt>Canceladas</dt><dd>{informe.reservas.canceladas}</dd></div>
                <div><dt>Pases usados</dt><dd>{informe.reservas.pases_usados} de {informe.reservas.pases_emitidos}</dd></div>
                <div><dt>Garantizadas sin llegada</dt><dd>{informe.reservas.garantizadas_sin_llegada}</dd></div>
              </dl>
            </div>
            <div className="informe-bloque">
              <h3>Inventario crítico</h3>
              <ListaCritica titulo="Agotados" items={informe.inventario.agotados} />
              <ListaCritica titulo="En nivel mínimo" items={informe.inventario.en_minimo} />
              {informe.inventario.mayor_consumo_evento.length > 0 && (
                <>
                  <p className="informe-lista-critica"><strong>Mayor consumo en el evento:</strong></p>
                  <ul className="informe-consumo">
                    {informe.inventario.mayor_consumo_evento.map((c) => (
                      <li key={c.nombre}>{c.nombre}: {c.cantidad} {c.unidad}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div className="informe-bloque">
              <h3>Alertas y clientes</h3>
              <dl>
                <div><dt>Alertas altas</dt><dd>{informe.alertas_activas.alto}</dd></div>
                <div><dt>Alertas medias</dt><dd>{informe.alertas_activas.medio}</dd></div>
                <div><dt>Alertas bajas</dt><dd>{informe.alertas_activas.bajo}</dd></div>
                <div><dt>Conversaciones (7 días)</dt><dd>{informe.sentimiento.conversaciones_7d}</dd></div>
                <div><dt>Escaladas abiertas</dt><dd>{informe.sentimiento.escaladas_abiertas}</dd></div>
              </dl>
            </div>
            <div className="informe-bloque">
              <h3>Comisiones</h3>
              <dl>
                <div><dt>Pendientes</dt><dd>{formatoCOP(informe.comisiones.pendiente)}</dd></div>
                <div><dt>Liquidadas</dt><dd>{formatoCOP(informe.comisiones.liquidada)}</dd></div>
              </dl>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export function DashboardPage() {
  const [eventos, setEventos] = useState([]);
  const [eventoId, setEventoId] = useState(null);
  const [resumen, setResumen] = useState(null);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    listarEventos()
      .then((data) => {
        setEventos(data.items);
        if (data.items.length > 0) setEventoId(eventoInicial(data.items).id);
      })
      .catch((err) => setError(mensajeDeError(err)));
  }, []);

  async function cargarResumen(id) {
    if (!id) return;
    setCargando(true);
    setError(null);
    try {
      const data = await obtenerResumenEvento(id);
      setResumen(data);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar el resumen del evento"));
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => {
    cargarResumen(eventoId);
  }, [eventoId]);

  async function resolverAlerta(alertaId) {
    await actualizarAlerta(alertaId, "resuelta");
    cargarResumen(eventoId);
  }

  const porcentaje = resumen ? Math.round(resumen.porcentaje_aforo * 100) : 0;

  return (
    <div>
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">RESUMEN DE OPERACIÓN</p>
          <h1>Panel general</h1>
          <p className="page-subtitle">Aforo, accesos y comisiones del evento.</p>
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

      {resumen && (
        <>
          <div className="kpi-grid" style={{ marginBottom: "24px" }}>
            <KpiCard
              label="Aforo actual"
              value={`${resumen.accesos_validos} / ${resumen.aforo_maximo}`}
              hint={`${porcentaje}% de capacidad`}
            />
            <KpiCard label="Accesos duplicados" value={resumen.accesos_duplicados} />
            <KpiCard label="Accesos rechazados" value={resumen.accesos_rechazados} />
            <KpiCard
              label="Comisiones pendientes"
              value={formatoCOP(resumen.comisiones_pendientes)}
            />
            <KpiCard
              label="Comisiones liquidadas"
              value={formatoCOP(resumen.comisiones_liquidadas)}
            />
          </div>

          <div className="card dashboard-aforo" style={{ marginBottom: "20px" }}>
            <div className="section-heading"><div><p className="section-kicker">CAPACIDAD DEL EVENTO</p><h2>Aforo registrado</h2></div><BadgeNivel nivel={resumen.nivel_riesgo_general} /></div>
            <div className="aforo-bar-track">
              <div
                className={`aforo-bar-fill nivel-${resumen.nivel_riesgo_general}`}
                style={{ width: `${Math.min(porcentaje, 100)}%` }}
              />
            </div>
            <p className="aforo-bar-caption">
              {resumen.accesos_validos} ingresos válidos de {resumen.aforo_maximo} cupos —
              <span className="aforo-caption-divider" />Nivel de ocupación actual
            </p>
          </div>

          <div className="card dashboard-recommendation" style={{ marginBottom: "20px" }}>
            <p className="section-kicker">LECTURA DEL EVENTO</p>
            <h2>Recomendación operativa</h2>
            <p className="recommendation-copy">{resumen.recomendacion}</p>
          </div>

          <div className="card">
            <div className="section-heading"><div><p className="section-kicker">SEGUIMIENTO</p><h2>Alertas activas</h2></div><span className="alert-count">{resumen.alertas_activas.length}</span></div>
            {resumen.alertas_activas.length === 0 && (
              <p className="empty-state">No hay alertas activas para este evento.</p>
            )}
            {resumen.alertas_activas.map((alerta) => (
              <div key={alerta.id} className={`alert-banner nivel-${alerta.nivel}`}>
                <div style={{ flex: 1 }}>
                  <strong>{alerta.tipo_alerta.replace(/_/g, " ")}</strong>
                  <p style={{ margin: "4px 0 0 0" }}>{alerta.descripcion}</p>
                </div>
                <button
                  className="btn btn-outline btn-sm"
                  onClick={() => resolverAlerta(alerta.id)}
                >
                  Marcar resuelta
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {eventoId && <InformeJornada key={eventoId} eventoId={eventoId} />}

      {cargando && !resumen && <div className="card loading-state">Cargando resumen del evento…</div>}
    </div>
  );
}
