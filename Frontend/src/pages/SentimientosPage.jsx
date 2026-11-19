import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertBanner } from "../components/AlertBanner";
import { Badge } from "../components/Badge";
import { KpiCard } from "../components/KpiCard";
import { mensajeDeError } from "../services/apiClient";
import {
  analizarTexto,
  listarConversaciones,
  obtenerConversacion,
  obtenerPanelSentimientos,
  resolverConversacion,
} from "../services/sentimientosService";
import "./SentimientosPage.css";

const PERIODOS = [7, 14, 30];

const COLOR_ETIQUETA = {
  positivo: "var(--color-success)",
  neutral: "#76849a",
  negativo: "var(--color-danger)",
};
const TEXTO_ETIQUETA = { positivo: "Positivo", neutral: "Neutral", negativo: "Negativo" };
const VARIANTE_ETIQUETA = { positivo: "success", neutral: "neutral", negativo: "danger" };
const EMOCIONES = {
  alegria: { emoji: "😄", nombre: "Alegría" },
  sorpresa: { emoji: "😮", nombre: "Sorpresa" },
  neutral: { emoji: "😐", nombre: "Neutral" },
  molestia: { emoji: "😕", nombre: "Molestia" },
  enojo: { emoji: "😠", nombre: "Enojo" },
  tristeza: { emoji: "😢", nombre: "Tristeza" },
  miedo: { emoji: "😨", nombre: "Miedo" },
};
const PESTANAS = [
  { clave: "abiertas", texto: "Escaladas abiertas" },
  { clave: "escaladas", texto: "Escaladas" },
  { clave: "todas", texto: "Todas" },
];
const NOMBRE_CANAL = { web: "Chat web", whatsapp: "WhatsApp" };

function emojiAnimo(valor) {
  const v = Number(valor) || 0;
  if (v <= -0.6) return "😠";
  if (v <= -0.2) return "😕";
  if (v < 0.2) return "😐";
  if (v < 0.6) return "🙂";
  return "😍";
}

function textoPuntaje(valor) {
  const v = Number(valor) || 0;
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)}`;
}

function porcentaje(parte, total) {
  return total > 0 ? Math.round((parte / total) * 100) : 0;
}

function fechaCorta(iso) {
  const [, mes, dia] = String(iso).split("-");
  return `${dia}/${mes}`;
}

function fechaHora(iso) {
  return new Date(iso).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

function nombreAspecto(clave, mapa) {
  if (mapa[clave]) return mapa[clave];
  const texto = String(clave).replace(/_/g, " ");
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function simboloSentimiento(sentimiento) {
  if (sentimiento === "positivo") return "▲";
  if (sentimiento === "negativo") return "▼";
  return "●";
}

function Medidor({ valor, etiqueta }) {
  const v = Math.max(-1, Math.min(1, Number(valor) || 0));
  return (
    <div
      className="sent-medidor"
      role="meter"
      aria-label={etiqueta}
      aria-valuemin={-1}
      aria-valuemax={1}
      aria-valuenow={v}
      aria-valuetext={textoPuntaje(v)}
    >
      <div className="sent-medidor-pista">
        <span className="sent-medidor-marca" style={{ left: `${(v + 1) * 50}%` }} />
      </div>
      <div className="sent-medidor-escala" aria-hidden="true">
        <span>−1</span>
        <span>0</span>
        <span>+1</span>
      </div>
    </div>
  );
}

function ChipSentimiento({ sentimiento, puntaje, emocion }) {
  const info = EMOCIONES[emocion];
  return (
    <span className="sent-chip" style={{ "--chip-color": COLOR_ETIQUETA[sentimiento] ?? COLOR_ETIQUETA.neutral }}>
      <span aria-hidden="true">{info ? info.emoji : emojiAnimo(puntaje)}</span>
      {TEXTO_ETIQUETA[sentimiento] ?? "Sin análisis"}
      {puntaje !== null && puntaje !== undefined && <span className="sent-chip-valor">{textoPuntaje(puntaje)}</span>}
    </span>
  );
}

function ChipAspecto({ nombre, sentimiento }) {
  return (
    <span className="sent-chip sent-chip-aspecto" style={{ "--chip-color": COLOR_ETIQUETA[sentimiento] ?? COLOR_ETIQUETA.neutral }}>
      <span aria-hidden="true">{simboloSentimiento(sentimiento)}</span>
      {nombre}
      <span className="sr-only"> ({sentimiento})</span>
    </span>
  );
}

function Leyenda() {
  return (
    <ul className="sent-leyenda" aria-label="Leyenda">
      {Object.keys(COLOR_ETIQUETA).map((clave) => (
        <li key={clave}>
          <span className="sent-leyenda-punto" style={{ background: COLOR_ETIQUETA[clave] }} />
          {TEXTO_ETIQUETA[clave]}
        </li>
      ))}
    </ul>
  );
}

function GraficoTendencia({ datos }) {
  const n = datos.length;
  const ancho = Math.max(340, 70 + n * 22);
  const alto = 240;
  const margen = { izq: 34, der: 36, arriba: 12, abajo: 28 };
  const areaAncho = ancho - margen.izq - margen.der;
  const areaAlto = alto - margen.arriba - margen.abajo;
  const maxTotal = Math.max(1, ...datos.map((d) => d.positivo + d.neutral + d.negativo));
  const paso = areaAncho / n;
  const anchoBarra = Math.min(26, paso * 0.68);
  const yConteo = (v) => margen.arriba + areaAlto - (v / maxTotal) * areaAlto;
  const yPromedio = (v) => margen.arriba + areaAlto / 2 - (Math.max(-1, Math.min(1, v)) * areaAlto) / 2;
  const cadaCuanto = n <= 8 ? 1 : n <= 16 ? 2 : 4;
  const marcas = [...new Set([0, Math.round(maxTotal / 2), maxTotal])];

  const segmentos = [];
  let actual = [];
  datos.forEach((d, i) => {
    if (d.positivo + d.neutral + d.negativo > 0) {
      actual.push([margen.izq + paso * i + paso / 2, yPromedio(d.promedio)]);
    } else if (actual.length) {
      segmentos.push(actual);
      actual = [];
    }
  });
  if (actual.length) segmentos.push(actual);

  return (
    <div className="sent-grafico-scroll">
      <svg
        className="sent-grafico"
        viewBox={`0 0 ${ancho} ${alto}`}
        style={{ minWidth: `${ancho}px` }}
        role="img"
        aria-label="Mensajes por día según su sentimiento, con la línea del ánimo promedio"
      >
        {marcas.map((m) => (
          <g key={m}>
            <line className="sent-rejilla" x1={margen.izq} x2={ancho - margen.der} y1={yConteo(m)} y2={yConteo(m)} />
            <text className="sent-eje" x={margen.izq - 6} y={yConteo(m) + 4} textAnchor="end">{m}</text>
          </g>
        ))}
        {[1, 0, -1].map((m) => (
          <text key={m} className="sent-eje sent-eje-prom" x={ancho - margen.der + 6} y={yPromedio(m) + 4}>
            {m > 0 ? "+1" : m < 0 ? "−1" : "0"}
          </text>
        ))}
        {datos.map((d, i) => {
          const x = margen.izq + paso * i + (paso - anchoBarra) / 2;
          const total = d.positivo + d.neutral + d.negativo;
          let base = margen.arriba + areaAlto;
          const tramos = ["positivo", "neutral", "negativo"].map((clave) => {
            const h = (d[clave] / maxTotal) * areaAlto;
            base -= h;
            return { clave, y: base, h };
          });
          return (
            <g key={d.fecha}>
              <title>
                {`${fechaCorta(d.fecha)}: ${d.positivo} positivos, ${d.neutral} neutrales, ${d.negativo} negativos`}
                {total > 0 ? ` · ánimo ${textoPuntaje(d.promedio)}` : " · sin mensajes"}
              </title>
              <rect x={margen.izq + paso * i} y={margen.arriba} width={paso} height={areaAlto} fill="transparent" />
              {tramos.map((t) => t.h > 0 && (
                <rect key={t.clave} x={x} y={t.y} width={anchoBarra} height={t.h} fill={COLOR_ETIQUETA[t.clave]} opacity="0.85" />
              ))}
              {i % cadaCuanto === 0 && (
                <text className="sent-eje" x={margen.izq + paso * i + paso / 2} y={alto - 8} textAnchor="middle">
                  {fechaCorta(d.fecha)}
                </text>
              )}
            </g>
          );
        })}
        {segmentos.map((seg, i) => (
          <polyline
            key={i}
            className="sent-linea"
            points={seg.map(([x, y]) => `${x},${y}`).join(" ")}
          />
        ))}
        {segmentos.flat().map(([x, y], i) => (
          <circle key={i} className="sent-punto" cx={x} cy={y} r="3" />
        ))}
      </svg>
    </div>
  );
}

function BarrasAspectos({ aspectos }) {
  const maximo = Math.max(1, ...aspectos.map((a) => a.positivo + a.neutral + a.negativo));
  return (
    <ul className="sent-aspectos">
      {aspectos.map((a) => {
        const total = a.positivo + a.neutral + a.negativo;
        let x = 0;
        const tramos = ["positivo", "neutral", "negativo"].map((clave) => {
          const w = (a[clave] / maximo) * 100;
          const tramo = { clave, x, w };
          x += w;
          return tramo;
        });
        return (
          <li key={a.aspecto}>
            <div className="sent-aspecto-cabecera">
              <span>{a.nombre}</span>
              <small>{total} {total === 1 ? "mención" : "menciones"}</small>
            </div>
            <svg
              className="sent-aspecto-barra"
              viewBox="0 0 100 10"
              preserveAspectRatio="none"
              role="img"
              aria-label={`${a.nombre}: ${a.positivo} positivas, ${a.neutral} neutrales, ${a.negativo} negativas`}
            >
              <rect x="0" y="0" width="100" height="10" fill="rgba(255,255,255,.05)" />
              {tramos.map((t) => t.w > 0 && (
                <rect key={t.clave} x={t.x} y="0" width={t.w} height="10" fill={COLOR_ETIQUETA[t.clave]} opacity="0.85">
                  <title>{`${TEXTO_ETIQUETA[t.clave]}: ${a[t.clave]}`}</title>
                </rect>
              ))}
            </svg>
          </li>
        );
      })}
    </ul>
  );
}

function TarjetaCanal({ canal, datos }) {
  const d = datos ?? {};
  const total = d.total ?? 0;
  return (
    <div className="sent-canal">
      <div className="sent-canal-cabecera">
        <strong>{NOMBRE_CANAL[canal]}</strong>
        <small>{total} {total === 1 ? "mensaje" : "mensajes"}</small>
      </div>
      <svg
        className="sent-canal-barra"
        viewBox="0 0 100 10"
        preserveAspectRatio="none"
        role="img"
        aria-label={`${NOMBRE_CANAL[canal]}: ${d.positivo ?? 0} positivos, ${d.neutral ?? 0} neutrales, ${d.negativo ?? 0} negativos`}
      >
        <rect x="0" y="0" width="100" height="10" fill="rgba(255,255,255,.05)" />
        {total > 0 && (() => {
          let x = 0;
          return ["positivo", "neutral", "negativo"].map((clave) => {
            const w = ((d[clave] ?? 0) / total) * 100;
            const rect = w > 0 && (
              <rect key={clave} x={x} y="0" width={w} height="10" fill={COLOR_ETIQUETA[clave]} opacity="0.85">
                <title>{`${TEXTO_ETIQUETA[clave]}: ${d[clave]}`}</title>
              </rect>
            );
            x += w;
            return rect;
          });
        })()}
      </svg>
      <dl className="sent-canal-datos">
        {["positivo", "neutral", "negativo"].map((clave) => (
          <div key={clave}>
            <dt><span className="sent-leyenda-punto" style={{ background: COLOR_ETIQUETA[clave] }} />{TEXTO_ETIQUETA[clave]}</dt>
            <dd>{d[clave] ?? 0} <small>({porcentaje(d[clave] ?? 0, total)}%)</small></dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

function DetalleConversacion({ detalle, mapaAspectos, onResolver, resolviendo, aviso, errorAccion }) {
  const esWeb = detalle.canal === "web";
  const mensajesUsuario = detalle.mensajes.filter((m) => m.autor === "usuario");
  return (
    <div className="sent-detalle">
      <div className="sent-detalle-cabecera">
        <div>
          <h3>{NOMBRE_CANAL[detalle.canal] ?? detalle.canal} · {detalle.id.slice(0, 8)}</h3>
          <small>Iniciada {fechaHora(detalle.creada_en)} · Última actividad {fechaHora(detalle.actualizada_en)}</small>
        </div>
        <div className="sent-detalle-estado">
          {detalle.escalada && (
            <Badge variante={detalle.escalada_resuelta ? "neutral" : "danger"}>
              {detalle.escalada_resuelta ? "Escalada resuelta" : "Escalada abierta"}
            </Badge>
          )}
          <Badge variante="neutral">{emojiAnimo(detalle.promedio)} ánimo {textoPuntaje(detalle.promedio)}</Badge>
        </div>
      </div>

      {detalle.contacto_humano && (
        <p className="sent-contacto">
          Dejó su contacto: <a href={`tel:${detalle.contacto_humano.replace(/[^\d+]/g, "")}`}>{detalle.contacto_humano}</a>
        </p>
      )}
      {detalle.reserva_id && <p className="sent-nota">Esta conversación terminó en la reserva #{detalle.reserva_id}.</p>}
      {!esWeb && (
        <p className="sent-privacidad">Por privacidad solo se guarda el análisis, no el texto ni el teléfono.</p>
      )}

      {detalle.escalada && !detalle.escalada_resuelta && (
        <div className="sent-detalle-acciones">
          <button type="button" className="btn btn-primary btn-sm" onClick={onResolver} disabled={resolviendo}>
            {resolviendo ? "Marcando…" : "Marcar como resuelta"}
          </button>
        </div>
      )}
      {aviso && <p className="sent-exito" role="status">{aviso}</p>}
      {errorAccion && <AlertBanner nivel="alto">{errorAccion}</AlertBanner>}

      {esWeb ? (
        <ol className="sent-transcripcion" aria-label="Transcripción">
          {detalle.mensajes.map((m, i) => (
            <li key={i} className={`sent-burbuja-fila ${m.autor === "usuario" ? "usuario" : "bot"}`}>
              <div className="sent-burbuja">
                <p>{m.texto ?? "(sin texto)"}</p>
                {m.autor === "usuario" && m.sentimiento && (
                  <div className="sent-burbuja-chips">
                    <ChipSentimiento sentimiento={m.sentimiento} puntaje={m.puntaje} emocion={m.emocion} />
                    {m.aspectos.map((par) => {
                      const [clave, sent] = par.split(":");
                      return <ChipAspecto key={par} nombre={nombreAspecto(clave, mapaAspectos)} sentimiento={sent} />;
                    })}
                  </div>
                )}
              </div>
              <small>{fechaHora(m.creado_en)}</small>
            </li>
          ))}
        </ol>
      ) : (
        <ol className="sent-transcripcion" aria-label="Análisis de los mensajes del cliente">
          {mensajesUsuario.length === 0 && <li className="empty-state">No hay mensajes analizados en esta conversación.</li>}
          {mensajesUsuario.map((m, i) => (
            <li key={i} className="sent-analisis-wa">
              <span className="sent-analisis-num">Mensaje {i + 1}</span>
              <div className="sent-burbuja-chips">
                <ChipSentimiento sentimiento={m.sentimiento} puntaje={m.puntaje} emocion={m.emocion} />
                {m.aspectos.map((par) => {
                  const [clave, sent] = par.split(":");
                  return <ChipAspecto key={par} nombre={nombreAspecto(clave, mapaAspectos)} sentimiento={sent} />;
                })}
              </div>
              <small>{fechaHora(m.creado_en)}</small>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function ProbadorAnalisis() {
  const idTexto = useId();
  const [texto, setTexto] = useState("");
  const [usarIa, setUsarIa] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");
  const [analizando, setAnalizando] = useState(false);

  async function analizar(event) {
    event.preventDefault();
    setError("");
    setResultado(null);
    setAnalizando(true);
    try {
      setResultado(await analizarTexto(texto.trim(), usarIa));
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo analizar el texto."));
    } finally {
      setAnalizando(false);
    }
  }

  const info = resultado ? EMOCIONES[resultado.emocion] : null;

  return (
    <section className="card sent-probador" aria-labelledby={`${idTexto}-titulo`}>
      <p className="section-kicker">HERRAMIENTA</p>
      <h2 id={`${idTexto}-titulo`}>Probador de análisis</h2>
      <p className="sent-nota">Pega un comentario para ver cómo lo interpreta el asistente. El texto no se guarda.</p>
      <form onSubmit={analizar}>
        <div className="form-field">
          <label htmlFor={idTexto}>Comentario o mensaje</label>
          <textarea
            id={idTexto}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            minLength={3}
            maxLength={2000}
            rows={5}
            placeholder="Ej. La música estuvo increíble, pero la fila de entrada fue eterna."
            required
          />
        </div>
        <div className="sent-probador-acciones">
          <label className="sent-casilla">
            <input type="checkbox" checked={usarIa} onChange={(e) => setUsarIa(e.target.checked)} />
            Analizar también con IA
          </label>
          <small>{texto.length}/2000</small>
          <button type="submit" className="btn btn-primary" disabled={analizando || texto.trim().length < 3}>
            {analizando ? "Analizando…" : "Analizar sentimiento"}
          </button>
        </div>
      </form>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}

      {resultado && (
        <div className="sent-resultado" aria-live="polite">
          <div className="sent-resultado-fila">
            <Badge variante={VARIANTE_ETIQUETA[resultado.etiqueta] ?? "neutral"}>
              {TEXTO_ETIQUETA[resultado.etiqueta] ?? resultado.etiqueta}
            </Badge>
            <span>{info ? `${info.emoji} ${info.nombre}` : resultado.emocion}</span>
            <span className="sent-nota">Intensidad {resultado.intensidad}</span>
            {typeof resultado.confianza === "number" && (
              <span className="sent-nota">Confianza {Math.round(resultado.confianza * 100)}%</span>
            )}
          </div>
          <div className="sent-resultado-puntaje">
            <span>Puntaje <strong>{textoPuntaje(resultado.puntaje)}</strong></span>
            <Medidor valor={resultado.puntaje} etiqueta="Puntaje de sentimiento" />
          </div>
          {resultado.urgente && (
            <AlertBanner nivel="alto">
              <div>
                <strong>Mensaje urgente.</strong> {resultado.motivo_urgencia}
              </div>
            </AlertBanner>
          )}
          {resultado.aspectos?.length > 0 && (
            <div>
              <h3>Aspectos detectados</h3>
              <div className="sent-burbuja-chips">
                {resultado.aspectos.map((a) => (
                  <ChipAspecto key={a.aspecto} nombre={a.nombre ?? a.aspecto} sentimiento={a.sentimiento} />
                ))}
              </div>
            </div>
          )}
          <div className="sent-evidencia">
            <p><strong>Términos positivos:</strong> {resultado.terminos_positivos?.join(", ") || "ninguno detectado"}</p>
            <p><strong>Términos negativos:</strong> {resultado.terminos_negativos?.join(", ") || "ninguno detectado"}</p>
          </div>
          <p className="sent-nota">Método: {resultado.metodo}</p>
          {resultado.aviso_ia && <p className="sent-nota">Nota sobre la IA: {resultado.aviso_ia}</p>}
        </div>
      )}
    </section>
  );
}

export function SentimientosPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const sesionId = searchParams.get("sesion");

  const [dias, setDias] = useState(14);
  const [panel, setPanel] = useState(null);
  const [cargandoPanel, setCargandoPanel] = useState(true);
  const [errorPanel, setErrorPanel] = useState("");
  const [versionPanel, setVersionPanel] = useState(0);

  const [pestana, setPestana] = useState("abiertas");
  const [conversaciones, setConversaciones] = useState([]);
  const [cargandoLista, setCargandoLista] = useState(true);
  const [errorLista, setErrorLista] = useState("");
  const [versionLista, setVersionLista] = useState(0);

  const [detalle, setDetalle] = useState(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [errorDetalle, setErrorDetalle] = useState("");
  const [resolviendo, setResolviendo] = useState(false);
  const [avisoResuelta, setAvisoResuelta] = useState("");
  const [errorAccion, setErrorAccion] = useState("");

  useEffect(() => {
    let activo = true;
    setCargandoPanel(true);
    setErrorPanel("");
    obtenerPanelSentimientos(dias)
      .then((datos) => { if (activo) setPanel(datos); })
      .catch((err) => { if (activo) setErrorPanel(mensajeDeError(err, "No fue posible cargar el panel de sentimientos.")); })
      .finally(() => { if (activo) setCargandoPanel(false); });
    return () => { activo = false; };
  }, [dias, versionPanel]);

  useEffect(() => {
    let activo = true;
    setCargandoLista(true);
    setErrorLista("");
    listarConversaciones({ estado: pestana, limite: 50 })
      .then((datos) => { if (activo) setConversaciones(datos); })
      .catch((err) => { if (activo) setErrorLista(mensajeDeError(err, "No fue posible cargar las conversaciones.")); })
      .finally(() => { if (activo) setCargandoLista(false); });
    return () => { activo = false; };
  }, [pestana, versionLista]);

  useEffect(() => {
    setAvisoResuelta("");
    setErrorAccion("");
    if (!sesionId) {
      setDetalle(null);
      setErrorDetalle("");
      return undefined;
    }
    let activo = true;
    setCargandoDetalle(true);
    setErrorDetalle("");
    obtenerConversacion(sesionId)
      .then((datos) => { if (activo) setDetalle(datos); })
      .catch((err) => {
        if (!activo) return;
        setDetalle(null);
        setErrorDetalle(mensajeDeError(err, "No fue posible abrir la conversación."));
      })
      .finally(() => { if (activo) setCargandoDetalle(false); });
    return () => { activo = false; };
  }, [sesionId]);

  const mapaAspectos = useMemo(() => {
    const mapa = {};
    (panel?.aspectos ?? []).forEach((a) => { mapa[a.aspecto] = a.nombre; });
    return mapa;
  }, [panel]);

  const abrirConversacion = useCallback((id) => {
    setSearchParams(id ? { sesion: id } : {}, { replace: true });
  }, [setSearchParams]);

  async function resolver() {
    if (!detalle) return;
    setResolviendo(true);
    setErrorAccion("");
    setAvisoResuelta("");
    try {
      const resumen = await resolverConversacion(detalle.id);
      setDetalle((actual) => (actual ? { ...actual, ...resumen } : actual));
      setAvisoResuelta("Conversación marcada como resuelta.");
      setVersionLista((v) => v + 1);
      setVersionPanel((v) => v + 1);
    } catch (err) {
      setErrorAccion(mensajeDeError(err, "No fue posible marcar la conversación como resuelta."));
    } finally {
      setResolviendo(false);
    }
  }

  const totales = panel?.totales;
  const sinDatos = totales && totales.mensajes === 0;
  const abiertas = totales?.escaladas_abiertas ?? 0;
  const detalleVisible = detalle && detalle.id === sesionId ? detalle : null;

  return (
    <div className="sentimientos-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">ASISTENTE DE IA</p>
          <h1>Centro de sentimientos</h1>
          <p className="page-subtitle">Cómo se sienten los clientes que hablan con el asistente, por tema, día y canal.</p>
        </div>
        <div className="sent-periodos" role="group" aria-label="Periodo de análisis">
          {PERIODOS.map((p) => (
            <button
              key={p}
              type="button"
              className={`sent-periodo${dias === p ? " activo" : ""}`}
              aria-pressed={dias === p}
              onClick={() => setDias(p)}
            >
              {p} días
            </button>
          ))}
        </div>
      </div>

      {errorPanel && <AlertBanner nivel="alto">{errorPanel}</AlertBanner>}
      {cargandoPanel && !panel && <div className="card sent-cargando" role="status">Cargando sentimientos…</div>}

      {totales && (
        <>
          <div className="kpi-grid" aria-busy={cargandoPanel}>
            <KpiCard label="Mensajes analizados" value={totales.mensajes} hint={`Últimos ${panel.periodo_dias} días`} />
            <KpiCard
              label="Positivos"
              value={`${porcentaje(totales.positivo, totales.mensajes)}%`}
              hint={`${totales.positivo} mensajes`}
            />
            <KpiCard
              label="Negativos"
              value={`${porcentaje(totales.negativo, totales.mensajes)}%`}
              hint={`${totales.negativo} mensajes`}
            />
            <div className="kpi-card sent-kpi-animo">
              <div className="kpi-label">Ánimo promedio</div>
              <div className="kpi-value">
                <span aria-hidden="true">{emojiAnimo(totales.promedio)}</span> {textoPuntaje(totales.promedio)}
              </div>
              <Medidor valor={totales.promedio} etiqueta="Ánimo promedio de los clientes" />
            </div>
            <KpiCard label="Conversaciones" value={totales.sesiones} hint="Sesiones iniciadas" />
            <div className={`kpi-card${abiertas > 0 ? " sent-kpi-alerta" : ""}`}>
              <div className="kpi-label">Escaladas abiertas</div>
              <div className="kpi-value">{abiertas}</div>
              <div className="kpi-hint">{abiertas > 0 ? "Clientes molestos por atender" : "Todo al día"}</div>
            </div>
          </div>

          {sinDatos ? (
            <section className="card">
              <p className="empty-state">
                Aún no hay mensajes analizados en este periodo. Esta información se llena sola con las
                conversaciones del asistente en el chat web y en WhatsApp.
              </p>
            </section>
          ) : (
            <>
              <section className="card" aria-labelledby="sent-tendencia">
                <div className="section-heading">
                  <div>
                    <p className="section-kicker">EVOLUCIÓN</p>
                    <h2 id="sent-tendencia">Tendencia por día</h2>
                  </div>
                  <Leyenda />
                </div>
                <GraficoTendencia datos={panel.tendencia} />
                <p className="sent-nota">
                  Las columnas cuentan mensajes por sentimiento (eje izquierdo); la línea azul es el ánimo promedio
                  del día (eje derecho, de −1 a +1).
                </p>
                <details className="sent-detalles-datos">
                  <summary>Ver datos en tabla</summary>
                  <div className="table-scroll">
                    <table className="data-table">
                      <thead>
                        <tr><th>Día</th><th>Positivos</th><th>Neutrales</th><th>Negativos</th><th>Ánimo</th></tr>
                      </thead>
                      <tbody>
                        {panel.tendencia.map((d) => (
                          <tr key={d.fecha}>
                            <td>{fechaCorta(d.fecha)}</td>
                            <td>{d.positivo}</td>
                            <td>{d.neutral}</td>
                            <td>{d.negativo}</td>
                            <td>{d.positivo + d.neutral + d.negativo > 0 ? textoPuntaje(d.promedio) : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              </section>

              <div className="sent-dos-columnas">
                <section className="card" aria-labelledby="sent-aspectos">
                  <div className="section-heading">
                    <div>
                      <p className="section-kicker">TEMAS</p>
                      <h2 id="sent-aspectos">Aspectos más mencionados</h2>
                    </div>
                    <Leyenda />
                  </div>
                  {panel.aspectos.length === 0 ? (
                    <p className="empty-state">Todavía no se detectan aspectos (música, servicio, precios…) en los mensajes.</p>
                  ) : (
                    <BarrasAspectos aspectos={panel.aspectos} />
                  )}
                </section>

                <div className="sent-columna">
                  <section className="card" aria-labelledby="sent-emociones">
                    <p className="section-kicker">TONO</p>
                    <h2 id="sent-emociones">Emociones detectadas</h2>
                    {panel.emociones.length === 0 ? (
                      <p className="empty-state">Sin emociones registradas.</p>
                    ) : (
                      <ul className="sent-emociones">
                        {panel.emociones.map((e) => {
                          const info = EMOCIONES[e.emocion] ?? { emoji: "💬", nombre: e.emocion };
                          return (
                            <li key={e.emocion} className="sent-chip sent-chip-emocion">
                              <span aria-hidden="true">{info.emoji}</span>
                              {info.nombre}
                              <strong>{e.total}</strong>
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </section>
                  <section className="card" aria-labelledby="sent-canales">
                    <p className="section-kicker">COMPARATIVO</p>
                    <h2 id="sent-canales">Canales</h2>
                    <div className="sent-canales">
                      <TarjetaCanal canal="web" datos={panel.por_canal.web} />
                      <TarjetaCanal canal="whatsapp" datos={panel.por_canal.whatsapp} />
                    </div>
                  </section>
                </div>
              </div>
            </>
          )}
        </>
      )}

      <section className="card" aria-labelledby="sent-conversaciones">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SEGUIMIENTO</p>
            <h2 id="sent-conversaciones">Conversaciones</h2>
          </div>
        </div>
        <div className="sent-pestanas" role="tablist" aria-label="Filtrar conversaciones">
          {PESTANAS.map((p) => (
            <button
              key={p.clave}
              type="button"
              role="tab"
              id={`sent-tab-${p.clave}`}
              aria-selected={pestana === p.clave}
              aria-controls="sent-lista-panel"
              className={`sent-pestana${pestana === p.clave ? " activa" : ""}`}
              onClick={() => setPestana(p.clave)}
            >
              {p.texto}
            </button>
          ))}
        </div>

        <div className="sent-conversaciones">
          <div id="sent-lista-panel" role="tabpanel" aria-labelledby={`sent-tab-${pestana}`} className="sent-lista-caja">
            {errorLista && <AlertBanner nivel="alto">{errorLista}</AlertBanner>}
            {cargandoLista && conversaciones.length === 0 && <p className="empty-state" role="status">Cargando conversaciones…</p>}
            {!cargandoLista && !errorLista && conversaciones.length === 0 && (
              <p className="empty-state">
                {pestana === "abiertas"
                  ? "No hay conversaciones escaladas pendientes."
                  : "No hay conversaciones en esta vista todavía."}
              </p>
            )}
            <ul className="sent-lista">
              {conversaciones.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`sent-item${c.id === sesionId ? " activo" : ""}`}
                    aria-current={c.id === sesionId ? "true" : undefined}
                    onClick={() => abrirConversacion(c.id)}
                  >
                    <span className="sent-item-animo" aria-hidden="true">{emojiAnimo(c.promedio)}</span>
                    <span className="sent-item-texto">
                      <strong>{NOMBRE_CANAL[c.canal] ?? c.canal} · {c.id.slice(0, 8)}</strong>
                      <small>
                        {c.mensajes_total} mensajes · {c.negativos} negativos · {fechaHora(c.actualizada_en)}
                      </small>
                    </span>
                    {c.escalada && (
                      <Badge variante={c.escalada_resuelta ? "neutral" : "danger"}>
                        {c.escalada_resuelta ? "Resuelta" : "Abierta"}
                      </Badge>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="sent-detalle-caja" aria-live="polite">
            {!sesionId && !cargandoDetalle && (
              <p className="empty-state">Elige una conversación para ver su detalle.</p>
            )}
            {sesionId && cargandoDetalle && !detalleVisible && <p className="empty-state" role="status">Abriendo conversación…</p>}
            {errorDetalle && <AlertBanner nivel="alto">{errorDetalle}</AlertBanner>}
            {detalleVisible && (
              <>
                <div className="sent-detalle-cerrar">
                  <button type="button" className="btn btn-outline btn-sm" onClick={() => abrirConversacion(null)}>
                    Cerrar detalle
                  </button>
                </div>
                <DetalleConversacion
                  detalle={detalleVisible}
                  mapaAspectos={mapaAspectos}
                  onResolver={resolver}
                  resolviendo={resolviendo}
                  aviso={avisoResuelta}
                  errorAccion={errorAccion}
                />
              </>
            )}
          </div>
        </div>
      </section>

      <ProbadorAnalisis />
    </div>
  );
}
