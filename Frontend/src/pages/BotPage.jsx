import { useCallback, useEffect, useId, useRef, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { Badge } from "../components/Badge";
import { apiClient, mensajeDeError } from "../services/apiClient";
import {
  diagnosticarWhatsApp,
  guardarConfiguracionBot,
  obtenerConfiguracionBot,
  obtenerEstadoBot,
  probarAsistente,
  probarConexionIA,
  probarWhatsApp,
} from "../services/botService";
import "./BotPage.css";

const SUGERENCIAS = ["Hola", "¿Qué eventos hay este fin de semana?", "Quiero reservar una mesa", "Estoy muy molesto con la atención"];

function urlBaseApi() {
  const base = String(apiClient.defaults.baseURL ?? "");
  const sinVersion = base.replace(/\/api\/v1\/?$/, "").replace(/\/$/, "");
  return sinVersion || window.location.origin;
}

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
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`;
}

function BotonCopiar({ texto, etiqueta }) {
  const [estado, setEstado] = useState("");
  const temporizador = useRef(null);

  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  async function copiar() {
    let resultado = "copiado";
    try {
      await navigator.clipboard.writeText(texto);
    } catch {
      resultado = "error";
    }
    setEstado(resultado);
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => setEstado(""), 2500);
  }

  return (
    <button type="button" className="btn btn-outline btn-sm" onClick={copiar} aria-label={etiqueta}>
      {estado === "copiado" ? "Copiado" : estado === "error" ? "No se pudo copiar" : "Copiar"}
    </button>
  );
}

function ResultadoPrueba({ resultado }) {
  if (!resultado) return null;
  return (
    <p className={`bot-resultado ${resultado.ok ? "ok" : "fallo"}`} role="status">
      <strong>{resultado.ok ? "Correcto" : "Falló"}</strong>
      {" · "}
      {resultado.detalle}
      {typeof resultado.milisegundos === "number" && ` (${resultado.milisegundos} ms)`}
    </p>
  );
}

function EstadoConexiones({ estado }) {
  const [probandoIa, setProbandoIa] = useState(false);
  const [resultadoIa, setResultadoIa] = useState(null);
  const [telefono, setTelefono] = useState("");
  const [enviandoWa, setEnviandoWa] = useState(false);
  const [resultadoWa, setResultadoWa] = useState(null);
  const [diagnosticando, setDiagnosticando] = useState(false);
  const [diagnostico, setDiagnostico] = useState(null);
  const idTel = useId();

  async function diagnosticar() {
    setDiagnosticando(true);
    setDiagnostico(null);
    try {
      setDiagnostico(await diagnosticarWhatsApp());
    } catch (err) {
      setDiagnostico({
        ok: false,
        pasos: [{ clave: "error", titulo: "Diagnóstico", ok: false, detalle: mensajeDeError(err, "No se pudo ejecutar el diagnóstico.") }],
      });
    } finally {
      setDiagnosticando(false);
    }
  }

  const urlWebhook = `${urlBaseApi()}${estado.webhook_ruta}`;
  const uso = estado.ia_limite_diario > 0 ? Math.min(100, Math.round((estado.ia_llamadas_hoy / estado.ia_limite_diario) * 100)) : 0;
  const pendientes = estado.checklist.filter((paso) => !paso.ok).length;

  async function probarIa() {
    setProbandoIa(true);
    setResultadoIa(null);
    try {
      setResultadoIa(await probarConexionIA());
    } catch (err) {
      setResultadoIa({ ok: false, detalle: mensajeDeError(err, "No se pudo probar la conexión con la IA.") });
    } finally {
      setProbandoIa(false);
    }
  }

  async function enviarWa(event) {
    event.preventDefault();
    setEnviandoWa(true);
    setResultadoWa(null);
    try {
      setResultadoWa(await probarWhatsApp({ telefono: telefono.trim() }));
    } catch (err) {
      setResultadoWa({ ok: false, detalle: mensajeDeError(err, "No se pudo enviar el aviso de prueba.") });
    } finally {
      setEnviandoWa(false);
    }
  }

  return (
    <section className="card" aria-labelledby="bot-estado">
      <div className="bot-seccion-cabecera">
        <div>
          <p className="bot-kicker">CONEXIONES</p>
          <h2 id="bot-estado">Estado de conexiones</h2>
        </div>
        <Badge variante={pendientes === 0 ? "success" : "accent"}>
          {pendientes === 0 ? "Todo listo" : `${pendientes} ${pendientes === 1 ? "paso pendiente" : "pasos pendientes"}`}
        </Badge>
      </div>

      <ul className="bot-checklist">
        {estado.checklist.map((paso) => (
          <li key={paso.clave} className={paso.ok ? "ok" : "pendiente"}>
            <span className="bot-check-icono" aria-hidden="true">{paso.ok ? "✓" : "•"}</span>
            <div>
              <strong>{paso.titulo}</strong>
              <small>{paso.detalle}</small>
            </div>
            <span className="bot-check-estado">{paso.ok ? "Listo" : "Pendiente"}</span>
          </li>
        ))}
      </ul>

      <div className="bot-tarjetas">
        <article className="bot-tarjeta" aria-labelledby="bot-t-ia">
          <div className="bot-tarjeta-titulo">
            <h3 id="bot-t-ia">Inteligencia artificial</h3>
            <Badge variante={estado.ia_activa ? "success" : "neutral"}>{estado.ia_activa ? "Activa" : "Motor local"}</Badge>
          </div>
          <p className="bot-dato">{estado.ia_proveedor}</p>
          <p className="bot-dato-sec">Modelo: <code>{estado.ia_modelo}</code></p>
          <div className="bot-uso">
            <div
              className="bot-uso-pista"
              role="progressbar"
              aria-label="Consultas a la IA hoy"
              aria-valuemin={0}
              aria-valuemax={estado.ia_limite_diario}
              aria-valuenow={Math.min(estado.ia_llamadas_hoy, estado.ia_limite_diario)}
            >
              <span style={{ width: `${uso}%` }} />
            </div>
            <small>{estado.ia_llamadas_hoy} de {estado.ia_limite_diario} consultas hoy</small>
          </div>
          <button type="button" className="btn btn-outline btn-sm" onClick={probarIa} disabled={probandoIa}>
            {probandoIa ? "Probando…" : "Probar conexión con la IA"}
          </button>
          <ResultadoPrueba resultado={resultadoIa} />
        </article>

        <article className="bot-tarjeta" aria-labelledby="bot-t-wa">
          <div className="bot-tarjeta-titulo">
            <h3 id="bot-t-wa">WhatsApp</h3>
            <Badge variante={estado.whatsapp_credenciales && estado.whatsapp_webhook ? "success" : "accent"}>
              {estado.whatsapp_credenciales && estado.whatsapp_webhook ? "Conectado" : "Incompleto"}
            </Badge>
          </div>
          <p className="bot-dato-sec">URL del webhook para Meta</p>
          <div className="bot-copiable">
            <code>{urlWebhook}</code>
            <BotonCopiar texto={urlWebhook} etiqueta="Copiar la URL del webhook" />
          </div>
          <small className="bot-nota">Meta solo acepta direcciones públicas con https; en local usa un túnel (por ejemplo ngrok).</small>
          <form onSubmit={enviarWa} className="bot-form-wa">
            <label htmlFor={idTel}>Teléfono para el aviso de prueba</label>
            <div className="bot-fila-input">
              <input
                id={idTel}
                type="tel"
                inputMode="tel"
                value={telefono}
                onChange={(e) => setTelefono(e.target.value)}
                placeholder="57 300 123 4567"
                minLength={7}
                maxLength={24}
                pattern="[0-9+()\-\s]+"
                required
              />
              <button type="submit" className="btn btn-outline btn-sm" disabled={enviandoWa || telefono.trim().length < 7}>
                {enviandoWa ? "Enviando…" : "Enviar aviso de prueba"}
              </button>
            </div>
            <small className="bot-nota">Se envía el aviso real (plantilla aprobada). Con el número de prueba de Meta, el teléfono debe estar en su lista de destinatarios.</small>
          </form>
          <ResultadoPrueba resultado={resultadoWa} />
          <button type="button" className="btn btn-outline btn-sm" onClick={diagnosticar} disabled={diagnosticando}>
            {diagnosticando ? "Diagnosticando…" : "Diagnosticar aviso de reservas"}
          </button>
          <small className="bot-nota">Revisa variables, token y número, y envía el aviso real de reserva (con datos de prueba) al destino configurado.</small>
          {diagnostico && (
            <ul className="bot-diagnostico" role="status" aria-label="Resultado del diagnóstico de WhatsApp">
              {diagnostico.pasos.map((p) => (
                <li key={p.clave} className={p.ok ? "ok" : "fallo"}>
                  <span aria-hidden="true">{p.ok ? "✓" : "✕"}</span>
                  <div>
                    <strong>{p.titulo}</strong>
                    <small>{p.detalle}</small>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </article>

        <article className="bot-tarjeta" aria-labelledby="bot-t-web">
          <div className="bot-tarjeta-titulo">
            <h3 id="bot-t-web">Chat web</h3>
            <Badge variante={estado.chat_web_activo ? "success" : "neutral"}>{estado.chat_web_activo ? "Activo" : "En pausa"}</Badge>
          </div>
          <p className="bot-dato-sec">Página pública de reservas</p>
          <div className="bot-copiable">
            <code>{estado.chat_web_url}</code>
            <BotonCopiar texto={estado.chat_web_url} etiqueta="Copiar la URL del chat web" />
          </div>
          <a className="btn btn-outline btn-sm" href={estado.chat_web_url} target="_blank" rel="noopener noreferrer">
            Abrir en una pestaña nueva
          </a>
        </article>
      </div>
    </section>
  );
}

function GuiaConexion() {
  return (
    <details className="card bot-guia">
      <summary>Guía de conexión paso a paso</summary>
      <ol>
        <li>
          <strong>Activar la IA.</strong> Crea una clave gratuita en Google AI Studio (aistudio.google.com/apikey) y guárdala en el archivo{" "}
          <code>.env</code> del backend como <code>GEMINI_API_KEY</code>. Reinicia el backend y usa «Probar conexión con la IA».
        </li>
        <li>
          <strong>Configurar el webhook en Meta.</strong> En tu app de WhatsApp Cloud API, pega la URL del webhook que aparece arriba
          y escribe el token de verificación definido en <code>WHATSAPP_WEBHOOK_VERIFY_TOKEN</code>. Suscribe el campo{" "}
          <code>messages</code>.
        </li>
        <li>
          <strong>Firmar los mensajes.</strong> Copia el App Secret de tu app de Meta en <code>WHATSAPP_APP_SECRET</code> para
          que el backend valide que los mensajes vienen de Meta.
        </li>
        <li>
          <strong>Credenciales de envío.</strong> Define <code>WHATSAPP_PHONE_NUMBER_ID</code> y{" "}
          <code>WHATSAPP_ACCESS_TOKEN</code> en el <code>.env</code>.
        </li>
        <li>
          <strong>Plantillas aprobadas.</strong> Crea y aprueba en Meta las plantillas de confirmación y de inventario; luego
          escribe sus nombres en <code>WHATSAPP_CONFIRMATION_TEMPLATE_NAME</code> y <code>WHATSAPP_INVENTORY_TEMPLATE_NAME</code>.
        </li>
        <li>
          <strong>Verificar.</strong> Reinicia el backend y revisa que todos los pasos del estado de conexiones aparezcan como
          «Listo». Esta pantalla nunca muestra los valores secretos.
        </li>
      </ol>
    </details>
  );
}

function CampoConfig({ campo, valor, onCambio, onRestaurar }) {
  const id = useId();
  const esDefecto = valor === campo.defecto;
  let control;
  if (campo.tipo === "bool") {
    const activo = valor === "true";
    control = (
      <button
        type="button"
        id={id}
        role="switch"
        aria-checked={activo}
        className={`bot-interruptor${activo ? " activo" : ""}`}
        onClick={() => onCambio(activo ? "false" : "true")}
      >
        <span className="bot-interruptor-perilla" />
        <span className="bot-interruptor-texto">{activo ? "Sí" : "No"}</span>
      </button>
    );
  } else if (campo.tipo === "entero") {
    control = <input id={id} type="number" min="1" max="100000" step="1" value={valor} onChange={(e) => onCambio(e.target.value)} />;
  } else if (campo.tipo === "hora") {
    control = <input id={id} type="time" value={valor} onChange={(e) => onCambio(e.target.value)} />;
  } else if (campo.defecto.length > 60 || valor.length > 60) {
    control = <textarea id={id} rows={4} maxLength={600} value={valor} onChange={(e) => onCambio(e.target.value)} />;
  } else {
    control = <input id={id} type="text" maxLength={600} value={valor} onChange={(e) => onCambio(e.target.value)} />;
  }

  return (
    <div className="form-field bot-campo">
      <label htmlFor={id}>{campo.descripcion}</label>
      {control}
      <div className="bot-campo-pie">
        <small>{campo.clave}</small>
        <button type="button" className="bot-enlace" onClick={onRestaurar} disabled={esDefecto}>
          Restaurar valor por defecto
        </button>
      </div>
    </div>
  );
}

function ConfiguracionBot({ onGuardado }) {
  const [config, setConfig] = useState(null);
  const [borrador, setBorrador] = useState({});
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState("");
  const [errorGuardar, setErrorGuardar] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState("");
  const [intento, setIntento] = useState(0);
  const temporizador = useRef(null);

  useEffect(() => {
    let activo = true;
    setCargando(true);
    setErrorCarga("");
    obtenerConfiguracionBot()
      .then((datos) => {
        if (!activo) return;
        setConfig(datos);
        setBorrador(datos.valores);
      })
      .catch((err) => { if (activo) setErrorCarga(mensajeDeError(err, "No fue posible cargar la configuración.")); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
  }, [intento]);

  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  const cambiados = config ? config.campos.filter((c) => borrador[c.clave] !== config.valores[c.clave]) : [];

  async function guardar(event) {
    event.preventDefault();
    if (cambiados.length === 0) return;
    setGuardando(true);
    setErrorGuardar("");
    setAviso("");
    const cambios = {};
    cambiados.forEach((c) => {
      const valor = borrador[c.clave];
      cambios[c.clave] = c.tipo === "bool" ? valor === "true" : valor;
    });
    try {
      const datos = await guardarConfiguracionBot(cambios);
      setConfig(datos);
      setBorrador(datos.valores);
      setAviso("Cambios guardados.");
      window.clearTimeout(temporizador.current);
      temporizador.current = window.setTimeout(() => setAviso(""), 4000);
      onGuardado?.();
    } catch (err) {
      setErrorGuardar(mensajeDeError(err, "No fue posible guardar los cambios."));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <section className="card" aria-labelledby="bot-config">
      <p className="bot-kicker">PERSONALIDAD Y REGLAS</p>
      <h2 id="bot-config">Cómo responde el asistente</h2>
      {cargando && !config && <p className="bot-vacio" role="status">Cargando configuración…</p>}
      {errorCarga && (
        <>
          <AlertBanner nivel="alto">{errorCarga}</AlertBanner>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setIntento((n) => n + 1)}>Reintentar</button>
        </>
      )}
      {config && (
        <form onSubmit={guardar} noValidate>
          <div className="bot-config-grid">
            {config.campos.map((campo) => (
              <CampoConfig
                key={campo.clave}
                campo={campo}
                valor={borrador[campo.clave] ?? ""}
                onCambio={(valor) => setBorrador((actual) => ({ ...actual, [campo.clave]: valor }))}
                onRestaurar={() => setBorrador((actual) => ({ ...actual, [campo.clave]: campo.defecto }))}
              />
            ))}
          </div>
          {errorGuardar && <AlertBanner nivel="alto">{errorGuardar}</AlertBanner>}
          <div className="bot-config-acciones">
            <button type="submit" className="btn btn-primary" disabled={guardando || cambiados.length === 0}>
              {guardando ? "Guardando…" : "Guardar cambios"}
            </button>
            <small>
              {cambiados.length === 0 ? "No hay cambios por guardar." : `${cambiados.length} ${cambiados.length === 1 ? "campo modificado" : "campos modificados"}.`}
            </small>
          </div>
        </form>
      )}
      <div className="bot-toast-zona" role="status" aria-live="polite">
        {aviso && <div className="bot-toast">{aviso}</div>}
      </div>
    </section>
  );
}

function ProbadorAsistente() {
  const [mensajes, setMensajes] = useState([]);
  const [estado, setEstado] = useState(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const idTexto = useId();
  const lista = useRef(null);
  const montado = useRef(true);

  useEffect(() => {
    montado.current = true;
    return () => { montado.current = false; };
  }, []);

  useEffect(() => {
    if (lista.current) lista.current.scrollTop = lista.current.scrollHeight;
  }, [mensajes, enviando]);

  const enviar = useCallback(async ({ texto: mensaje, accion, etiqueta }) => {
    setError("");
    setEnviando(true);
    setMensajes((actuales) => [...actuales, { rol: "usuario", texto: etiqueta ?? mensaje }]);
    try {
      const datos = await probarAsistente({ texto: mensaje, accion, estado });
      if (!montado.current) return;
      setEstado(datos.estado);
      const respuesta = datos.respuesta;
      const sentimiento = respuesta.analisis;
      const nuevos = respuesta.mensajes.map((m, i) => ({
        rol: "bot",
        texto: m.texto,
        opciones: m.opciones ?? [],
        eventos: m.eventos ?? [],
        meta: i === respuesta.mensajes.length - 1
          ? { intencion: datos.intencion, analisis: sentimiento, ia: respuesta.ia_usada, escalada: respuesta.escalada, reserva: respuesta.reserva }
          : null,
      }));
      setMensajes((actuales) => [...actuales, ...nuevos]);
    } catch (err) {
      if (montado.current) setError(mensajeDeError(err, "El asistente no pudo responder."));
    } finally {
      if (montado.current) setEnviando(false);
    }
  }, [estado]);

  function enviarFormulario(event) {
    event.preventDefault();
    const limpio = texto.trim();
    if (!limpio || enviando) return;
    setTexto("");
    enviar({ texto: limpio });
  }

  function reiniciar() {
    setMensajes([]);
    setEstado(null);
    setError("");
    setTexto("");
  }

  const ultimoBot = (() => {
    for (let i = mensajes.length - 1; i >= 0; i -= 1) if (mensajes[i].rol === "bot") return i;
    return -1;
  })();

  return (
    <section className="card bot-probador" aria-labelledby="bot-probador">
      <div className="bot-seccion-cabecera">
        <div>
          <p className="bot-kicker">PRUEBAS</p>
          <h2 id="bot-probador">Probador del asistente</h2>
        </div>
        <button type="button" className="btn btn-outline btn-sm" onClick={reiniciar} disabled={enviando || mensajes.length === 0}>
          Reiniciar
        </button>
      </div>
      <p className="bot-modo-prueba">Modo prueba: no crea reservas ni notificaciones</p>

      <div className="bot-chat" ref={lista} role="log" aria-live="polite" aria-label="Conversación de prueba">
        {mensajes.length === 0 && (
          <div className="bot-chat-vacio">
            <p>Escríbele al asistente como lo haría un cliente, o prueba con una de estas frases:</p>
            <div className="bot-opciones">
              {SUGERENCIAS.map((s) => (
                <button key={s} type="button" className="bot-opcion" onClick={() => enviar({ texto: s })} disabled={enviando}>{s}</button>
              ))}
            </div>
          </div>
        )}
        {mensajes.map((m, i) => (
          <div key={i} className={`bot-fila ${m.rol}`}>
            <div className="bot-burbuja">{m.texto}</div>
            {m.eventos?.length > 0 && (
              <div className="bot-eventos">
                {m.eventos.map((e) => (
                  <div key={e.id} className="bot-evento">
                    <strong>{e.nombre}</strong>
                    <span>{e.fecha_texto}</span>
                    {e.tematica && <small>{e.tematica}</small>}
                  </div>
                ))}
              </div>
            )}
            {m.opciones?.length > 0 && (
              <div className="bot-opciones">
                {m.opciones.map((o) => (
                  <button
                    key={o.valor}
                    type="button"
                    className="bot-opcion"
                    disabled={enviando || i !== ultimoBot}
                    onClick={() => enviar({ accion: o.valor, etiqueta: o.label })}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            )}
            {m.meta && (
              <small className="bot-meta">
                intención: {m.meta.intencion}
                {m.meta.analisis && (
                  <> · sentimiento: <span aria-hidden="true">{emojiAnimo(m.meta.analisis.puntaje)}</span> {textoPuntaje(m.meta.analisis.puntaje)} ({m.meta.analisis.etiqueta})</>
                )}
                {" · "}{m.meta.ia ? "IA" : "local"}
                {m.meta.escalada && " · escalada al equipo (simulado)"}
                {m.meta.reserva && ` · reserva simulada #${m.meta.reserva.id}`}
              </small>
            )}
          </div>
        ))}
        {enviando && <div className="bot-fila bot"><div className="bot-burbuja bot-escribiendo" role="status">Escribiendo…</div></div>}
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}

      <form className="bot-chat-form" onSubmit={enviarFormulario}>
        <label htmlFor={idTexto} className="bot-sr">Mensaje de prueba</label>
        <input
          id={idTexto}
          type="text"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          maxLength={600}
          placeholder="Escribe un mensaje…"
          autoComplete="off"
        />
        <button type="submit" className="btn btn-primary" disabled={enviando || !texto.trim()}>Enviar</button>
      </form>
    </section>
  );
}

export function BotPage() {
  const [estado, setEstado] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let activo = true;
    setError("");
    obtenerEstadoBot()
      .then((datos) => { if (activo) setEstado(datos); })
      .catch((err) => { if (activo) setError(mensajeDeError(err, "No fue posible cargar el estado del asistente.")); })
      .finally(() => { if (activo) setCargando(false); });
    return () => { activo = false; };
  }, [version]);

  return (
    <div className="bot-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">ASISTENTE DE IA</p>
          <h1>Asistente y WhatsApp</h1>
          <p className="page-subtitle">Conecta la IA y WhatsApp, ajusta la personalidad del asistente y pruébalo sin riesgo.</p>
        </div>
      </div>

      {error && (
        <div>
          <AlertBanner nivel="alto">{error}</AlertBanner>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => { setCargando(true); setVersion((v) => v + 1); }}>
            Reintentar
          </button>
        </div>
      )}
      {cargando && !estado && !error && <div className="card bot-vacio" role="status">Cargando estado del asistente…</div>}
      {estado && <EstadoConexiones estado={estado} />}
      <GuiaConexion />
      <ConfiguracionBot onGuardado={() => setVersion((v) => v + 1)} />
      <ProbadorAsistente />
    </div>
  );
}
