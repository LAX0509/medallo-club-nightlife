import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { MiReservaVista } from "../components/MiReservaVista";
import { esVideoEvento, urlFlyerEvento } from "../services/eventosService";
import { enviarMensajeChat, obtenerEstadoChat, obtenerHistorialChat } from "../services/chatService";
import { copiarTexto } from "../services/pasesService";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import "./ReservaChatPage.css";

const CLAVE_SESION = "medallo_chat_sesion";
const CLAVE_ULTIMA_RESERVA = "medallo_ultima_reserva";
const CLAVE_ANALISIS = "medallo_chat_analisis";
const PAUSA_ENTRE_MENSAJES_MS = 500;
const TEXTO_MAXIMO = 600;

const EMOJI_ETIQUETA = { positivo: "😊", negativo: "😟", neutral: "😐", neutro: "😐", mixto: "🤔" };
const FLECHA_SENTIMIENTO = { positivo: "▲", negativo: "▼" };

function leerAlmacen(clave) {
  try {
    return window.localStorage.getItem(clave);
  } catch {
    return null;
  }
}

function escribirAlmacen(clave, valor) {
  try {
    window.localStorage.setItem(clave, valor);
  } catch {
    /* Sin almacenamiento disponible: la conversación sigue funcionando en memoria. */
  }
}

function borrarAlmacen(clave) {
  try {
    window.localStorage.removeItem(clave);
  } catch {
    /* Nada que limpiar. */
  }
}

function leerUltimaReserva() {
  try {
    const dato = JSON.parse(leerAlmacen(CLAVE_ULTIMA_RESERVA) || "null");
    return dato && dato.id && dato.token ? dato : null;
  } catch {
    return null;
  }
}

function capitalizar(texto) {
  const limpio = String(texto ?? "").replace(/_/g, " ").trim();
  return limpio.charAt(0).toUpperCase() + limpio.slice(1);
}

function mensajeDeFallo(err) {
  const estado = err?.response?.status;
  if (estado === 429) return err.response?.data?.detail || "Estás escribiendo muy rápido. Espera unos segundos y vuelve a intentarlo.";
  if (!err?.response) return "No pudimos conectar con el asistente. Revisa tu conexión a internet.";
  const detalle = err.response.data?.detail;
  if (typeof detalle === "string") return detalle;
  if (Array.isArray(detalle) && detalle.length > 0) return detalle.map((d) => d.msg ?? "").filter(Boolean).join(" · ");
  return "Algo salió mal de nuestro lado. Inténtalo de nuevo en un momento.";
}

function AnalisisChips({ analisis, escalada }) {
  if (!analisis) return null;
  const puntaje = Number(analisis.puntaje) || 0;
  const aspectos = analisis.aspectos ?? [];
  return (
    <div className="reserva-analisis" aria-label="Análisis de sentimiento del mensaje">
      <span className={`reserva-analisis-chip reserva-analisis-${analisis.etiqueta}`}>
        <span aria-hidden="true">{EMOJI_ETIQUETA[analisis.etiqueta] ?? "💬"}</span> {analisis.etiqueta} {puntaje > 0 ? "+" : ""}{puntaje.toFixed(2)}
      </span>
      {analisis.emocion && analisis.emocion !== "neutral" && (
        <span className="reserva-analisis-chip">{capitalizar(analisis.emocion)}</span>
      )}
      {aspectos.map((a) => (
        <span key={`${a.aspecto}-${a.sentimiento}`} className={`reserva-analisis-chip reserva-analisis-${a.sentimiento}`}>
          {capitalizar(a.nombre ?? a.aspecto)} {FLECHA_SENTIMIENTO[a.sentimiento] ?? "•"}
        </span>
      ))}
      {analisis.urgente && <span className="reserva-analisis-chip reserva-analisis-negativo">Urgente</span>}
      {escalada && <span className="reserva-analisis-nota">Avisamos al equipo</span>}
    </div>
  );
}

function TarjetaEvento({ evento, deshabilitada, onElegir }) {
  const flyer = urlFlyerEvento(evento.flyer_url);
  return (
    <button
      type="button"
      className={`reserva-opcion-evento${flyer ? " has-flyer" : ""}`}
      disabled={deshabilitada}
      onClick={() => onElegir(evento)}
    >
      {flyer &&
        (esVideoEvento(evento.flyer_url) ? (
          <video className="reserva-evento-flyer" src={flyer} muted loop playsInline preload="metadata" aria-hidden="true" />
        ) : (
          <img className="reserva-evento-flyer" src={flyer} alt="" loading="lazy" />
        ))}
      <span className="reserva-evento-detalle">
        <strong>{evento.nombre}</strong>
        <small>{evento.fecha_texto}{evento.tematica ? ` · ${evento.tematica}` : ""}</small>
      </span>
    </button>
  );
}

function TarjetaReserva({ reserva }) {
  const [copiado, setCopiado] = useState("");
  const temporizador = useRef(null);
  const enlaceGestion = `/reservas?reserva=${reserva.id}&token=${encodeURIComponent(reserva.token)}`;

  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  async function copiarEnlace() {
    const url = reserva.url || `${window.location.origin}${enlaceGestion}`;
    setCopiado((await copiarTexto(url)) ? "Enlace copiado" : "No se pudo copiar");
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => setCopiado(""), 2500);
  }

  return (
    <section className="reserva-tarjeta-reserva" aria-label={`Solicitud ${reserva.id} recibida`}>
      <p className="reserva-tarjeta-kicker">Listo</p>
      <h2>Solicitud #{reserva.id} recibida</h2>
      {reserva.evento_nombre && <p className="reserva-tarjeta-evento">{reserva.evento_nombre}</p>}
      <p className="reserva-tarjeta-texto">Guarda tu enlace privado: desde ahí ves el estado, tus pases QR y puedes cancelar si cambian los planes.</p>
      <div className="reserva-tarjeta-acciones">
        <Link className="btn btn-primary" to={enlaceGestion}>Ver y gestionar mi reserva</Link>
        <button className="btn btn-outline" type="button" onClick={copiarEnlace}>Copiar enlace</button>
      </div>
      <p className="reserva-tarjeta-copiado" role="status" aria-live="polite">{copiado}</p>
    </section>
  );
}

function ChatAsistente({ eventoInicialId, promotorId }) {
  const [estadoBot, setEstadoBot] = useState(null);
  const [mensajes, setMensajes] = useState([]);
  const [cargandoInicio, setCargandoInicio] = useState(true);
  const [escribiendo, setEscribiendo] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [fallo, setFallo] = useState(null);
  const [texto, setTexto] = useState("");
  const [mostrarAnalisis, setMostrarAnalisis] = useState(() => leerAlmacen(CLAVE_ANALISIS) === "1");

  const listaRef = useRef(null);
  const campoRef = useRef(null);
  const teniaFocoRef = useRef(false);
  const montadoRef = useRef(false);
  const iniciadoRef = useRef(false);
  const generacionRef = useRef(0);
  const sesionRef = useRef(null);
  const contadorRef = useRef(0);
  const temporizadoresRef = useRef(new Set());

  const nuevoId = () => {
    contadorRef.current += 1;
    return `m${contadorRef.current}`;
  };

  const vigente = (generacion) => montadoRef.current && generacion === generacionRef.current;

  const esperar = (ms) =>
    new Promise((resolver) => {
      const id = window.setTimeout(() => {
        temporizadoresRef.current.delete(id);
        resolver();
      }, ms);
      temporizadoresRef.current.add(id);
    });

  const turno = useCallback(async (carga, { etiquetaUsuario = null, reintento = null } = {}) => {
    const generacion = generacionRef.current;
    setEnviando(true);
    setFallo(null);
    let idUsuario = reintento?.idUsuario ?? null;
    if (!reintento && etiquetaUsuario) {
      idUsuario = nuevoId();
      setMensajes((actuales) => [...actuales, { id: idUsuario, autor: "usuario", texto: etiquetaUsuario }]);
    }
    setEscribiendo(true);

    let respuesta;
    try {
      const cuerpo = { ...carga };
      if (sesionRef.current) cuerpo.sesion_id = sesionRef.current;
      else if (promotorId) cuerpo.promotor_id = promotorId;
      respuesta = await enviarMensajeChat(cuerpo);
    } catch (err) {
      if (!vigente(generacion)) return false;
      setEscribiendo(false);
      setEnviando(false);
      setFallo({ mensaje: mensajeDeFallo(err), carga, idUsuario });
      return false;
    }
    if (!vigente(generacion)) return false;

    sesionRef.current = respuesta.sesion_id;
    escribirAlmacen(CLAVE_SESION, respuesta.sesion_id);
    if (idUsuario && respuesta.analisis) {
      setMensajes((actuales) =>
        actuales.map((m) => (m.id === idUsuario ? { ...m, analisis: respuesta.analisis, escalada: respuesta.escalada } : m))
      );
    }

    const reserva = respuesta.reserva && !respuesta.reserva.simulada && respuesta.reserva.token_cancelacion
      ? {
          id: respuesta.reserva.id,
          token: respuesta.reserva.token_cancelacion,
          url: respuesta.reserva.url_gestion,
          evento_nombre: respuesta.reserva.evento_nombre,
        }
      : null;
    if (reserva) escribirAlmacen(CLAVE_ULTIMA_RESERVA, JSON.stringify({ id: reserva.id, token: reserva.token, url: reserva.url }));

    const salida = respuesta.mensajes ?? [];
    for (let i = 0; i < salida.length; i += 1) {
      if (i > 0) {
        setEscribiendo(true);
        await esperar(PAUSA_ENTRE_MENSAJES_MS);
        if (!vigente(generacion)) return false;
      }
      setEscribiendo(false);
      const m = salida[i];
      setMensajes((actuales) => [
        ...actuales,
        { id: nuevoId(), autor: "bot", texto: m.texto, opciones: m.opciones ?? [], eventos: m.eventos ?? [] },
      ]);
    }
    if (reserva) {
      setEscribiendo(true);
      await esperar(PAUSA_ENTRE_MENSAJES_MS);
      if (!vigente(generacion)) return false;
      setMensajes((actuales) => [...actuales, { id: nuevoId(), autor: "reserva", reserva }]);
    }
    setEscribiendo(false);
    setEnviando(false);
    return true;
  }, [promotorId]);

  const iniciar = useCallback(async ({ aplicarEvento }) => {
    const generacion = generacionRef.current;
    setCargandoInicio(true);
    setFallo(null);

    let estado = null;
    try {
      estado = await obtenerEstadoChat();
    } catch {
      /* Sin estado se asume un asistente activo con el nombre por defecto. */
    }
    if (!vigente(generacion)) return;
    setEstadoBot(estado);
    if (estado && estado.activo === false) {
      setCargandoInicio(false);
      return;
    }

    const guardada = leerAlmacen(CLAVE_SESION);
    if (guardada) {
      try {
        const historial = await obtenerHistorialChat(guardada);
        if (!vigente(generacion)) return;
        if (historial.mensajes?.length) {
          sesionRef.current = historial.sesion_id;
          const restaurados = historial.mensajes.map((m) => ({ id: nuevoId(), autor: m.autor === "usuario" ? "usuario" : "bot", texto: m.texto }));
          const ultimo = restaurados[restaurados.length - 1];
          if (ultimo.autor === "bot") ultimo.opciones = historial.opciones ?? [];
          const guardadaReserva = leerUltimaReserva();
          if (historial.reserva_id && guardadaReserva && guardadaReserva.id === historial.reserva_id) {
            restaurados.push({ id: nuevoId(), autor: "reserva", reserva: { id: guardadaReserva.id, token: guardadaReserva.token, url: guardadaReserva.url } });
          }
          setMensajes(restaurados);
          setCargandoInicio(false);
          return;
        }
        borrarAlmacen(CLAVE_SESION);
      } catch (err) {
        if (!vigente(generacion)) return;
        if (err?.response?.status === 404) {
          borrarAlmacen(CLAVE_SESION);
        } else {
          setCargandoInicio(false);
          setFallo({ mensaje: mensajeDeFallo(err), reiniciar: true });
          return;
        }
      }
    }

    setCargandoInicio(false);
    sesionRef.current = null;
    if (!(await turno({ accion: "inicio" }))) return;
    if (aplicarEvento && eventoInicialId) {
      if (!(await turno({ accion: "reservar" }))) return;
      await turno({ accion: `evento:${eventoInicialId}` });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turno, eventoInicialId]);

  useEffect(() => {
    montadoRef.current = true;
    const temporizadores = temporizadoresRef.current;
    if (!iniciadoRef.current) {
      iniciadoRef.current = true;
      iniciar({ aplicarEvento: true });
    }
    return () => {
      montadoRef.current = false;
      temporizadores.forEach((id) => window.clearTimeout(id));
      temporizadores.clear();
    };
  }, [iniciar]);

  useEffect(() => {
    const lista = listaRef.current;
    if (!lista) return;
    const reducido = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    lista.scrollTo({ top: lista.scrollHeight, behavior: reducido ? "auto" : "smooth" });
  }, [mensajes, escribiendo, fallo]);

  useEffect(() => {
    if (!enviando && teniaFocoRef.current) {
      teniaFocoRef.current = false;
      campoRef.current?.focus();
    }
  }, [enviando]);

  function enviarTexto(evento) {
    evento.preventDefault();
    const limpio = texto.trim();
    if (!limpio || enviando) return;
    teniaFocoRef.current = document.activeElement === campoRef.current;
    setTexto("");
    turno({ texto: limpio }, { etiquetaUsuario: limpio });
  }

  function elegirOpcion(opcion) {
    if (enviando) return;
    turno({ texto: opcion.label, accion: opcion.valor }, { etiquetaUsuario: opcion.label });
  }

  function elegirEvento(evento) {
    if (enviando) return;
    turno({ accion: `evento:${evento.id}` }, { etiquetaUsuario: `${evento.nombre} · ${evento.fecha_texto}` });
  }

  function reintentar() {
    if (!fallo) return;
    if (fallo.reiniciar) {
      iniciar({ aplicarEvento: true });
      return;
    }
    turno(fallo.carga, { reintento: { idUsuario: fallo.idUsuario } });
  }

  function nuevaConversacion() {
    generacionRef.current += 1;
    temporizadoresRef.current.forEach((id) => window.clearTimeout(id));
    temporizadoresRef.current.clear();
    borrarAlmacen(CLAVE_SESION);
    sesionRef.current = null;
    setMensajes([]);
    setTexto("");
    setEnviando(false);
    setEscribiendo(false);
    setFallo(null);
    iniciar({ aplicarEvento: false });
  }

  function alternarAnalisis(evento) {
    setMostrarAnalisis(evento.target.checked);
    escribirAlmacen(CLAVE_ANALISIS, evento.target.checked ? "1" : "0");
  }

  const pausado = estadoBot?.activo === false;
  const nombreBot = estadoBot?.nombre_bot || "Asistente de Medallo Club";
  const lineaEstado = estadoBot?.ia ? "Asistente con IA" : "Asistente de reservas";

  let indiceUltimoBot = -1;
  for (let i = mensajes.length - 1; i >= 0; i -= 1) {
    if (mensajes[i].autor === "reserva") continue;
    if (mensajes[i].autor === "bot") indiceUltimoBot = i;
    break;
  }
  const ultimoBot = indiceUltimoBot >= 0 ? mensajes[indiceUltimoBot] : null;
  const opcionesRapidas = !enviando && !fallo && ultimoBot?.opciones?.length ? ultimoBot.opciones : [];

  return (
    <section className="reserva-chat-card" aria-label="Chat con el asistente de reservas">
      <header className="reserva-chat-header">
        <div className="reserva-bot-avatar" aria-hidden="true">M</div>
        <div className="reserva-chat-titulo">
          <strong>{nombreBot}</strong>
          <span><i aria-hidden="true" /> {pausado ? "En pausa" : lineaEstado}</span>
        </div>
        <button className="btn btn-outline btn-sm" type="button" onClick={nuevaConversacion} disabled={cargandoInicio}>
          Nueva conversación
        </button>
      </header>

      {pausado && (
        <p className="reserva-pausa" role="status">
          El asistente está en pausa por ahora. Vuelve a intentarlo más tarde o escríbenos directamente.
        </p>
      )}

      <div
        className="reserva-chat-messages"
        ref={listaRef}
        role="log"
        aria-live="polite"
        aria-relevant="additions"
        aria-busy={escribiendo || cargandoInicio}
      >
        {cargandoInicio && <p className="reserva-estado-chat" role="status">Conectando con el asistente…</p>}

        {mensajes.map((m, indice) => {
          if (m.autor === "reserva") return <TarjetaReserva key={m.id} reserva={m.reserva} />;
          if (m.autor === "usuario") {
            return (
              <div key={m.id} className="reserva-grupo-usuario">
                <div className="reserva-message reserva-message-usuario"><p>{m.texto}</p></div>
                {mostrarAnalisis && <AnalisisChips analisis={m.analisis} escalada={m.escalada} />}
              </div>
            );
          }
          const activo = indice === indiceUltimoBot && !enviando && !fallo;
          return (
            <div key={m.id} className="reserva-grupo-bot">
              <div className="reserva-message reserva-message-bot">
                <span className="reserva-message-avatar" aria-hidden="true">M</span>
                <p>{m.texto}</p>
              </div>
              {m.eventos?.length > 0 && (
                <div className="reserva-opciones reserva-opciones-eventos">
                  {m.eventos.map((evento) => (
                    <TarjetaEvento key={evento.id} evento={evento} deshabilitada={!activo} onElegir={elegirEvento} />
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {escribiendo && (
          <div className="reserva-message reserva-message-bot" role="status" aria-label={`${nombreBot} está escribiendo`}>
            <span className="reserva-message-avatar" aria-hidden="true">M</span>
            <p className="reserva-escribiendo" aria-hidden="true"><span /><span /><span /></p>
          </div>
        )}

        {fallo && (
          <div className="reserva-fallo" role="alert">
            <p>{fallo.mensaje}</p>
            <button className="btn btn-outline btn-sm" type="button" onClick={reintentar}>Reintentar</button>
          </div>
        )}

        {opcionesRapidas.length > 0 && (
          <div className="reserva-chips" role="group" aria-label="Respuestas rápidas">
            {opcionesRapidas.map((opcion) => (
              <button key={opcion.valor} type="button" className="reserva-chip" onClick={() => elegirOpcion(opcion)}>
                {opcion.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <form className="reserva-composer" onSubmit={enviarTexto}>
        <label className="sr-only-reserva" htmlFor="reserva-mensaje">Escribe tu mensaje</label>
        <input
          id="reserva-mensaje"
          ref={campoRef}
          type="text"
          value={texto}
          maxLength={TEXTO_MAXIMO}
          onChange={(evento) => setTexto(evento.target.value)}
          placeholder={pausado ? "El asistente está en pausa" : "Escribe tu mensaje…"}
          disabled={enviando || cargandoInicio || pausado}
          autoComplete="off"
          enterKeyHint="send"
        />
        <button className="btn btn-primary" type="submit" disabled={enviando || cargandoInicio || pausado || !texto.trim()}>
          Enviar
        </button>
      </form>

      <footer className="reserva-chat-footer">
        <label className="reserva-demo-check">
          <input type="checkbox" checked={mostrarAnalisis} onChange={alternarAnalisis} />
          <span>Mostrar análisis de sentimiento (modo demo)</span>
        </label>
        <p>Guardamos esta conversación para atenderte mejor. No compartas datos sensibles.</p>
      </footer>
    </section>
  );
}

export function ReservaChatPage() {
  const [parametros] = useSearchParams();
  const idReservaTexto = parametros.get("reserva") ?? parametros.get("cancelar");
  const idReserva = Number(idReservaTexto);
  const token = parametros.get("token") || "";
  const modoReserva = Number.isInteger(idReserva) && idReserva > 0 && token.length > 0;
  const eventoId = Number(parametros.get("evento"));
  const promotorId = Number(parametros.get("promotor"));

  return (
    <main className="reserva-publica">
      <header className="reserva-publica-header">
        <Link className="reserva-marca" to="/" aria-label="Volver al inicio de Medallo Club">
          <img className="reserva-marca-sello" src={medalloLogo} alt="" />
          <span><strong>MEDALLO CLUB</strong><small>Reservas</small></span>
        </Link>
        {modoReserva ? (
          <Link className="reserva-regreso" to="/reservas">Volver al asistente</Link>
        ) : (
          <Link className="reserva-regreso" to="/login">Acceso del equipo</Link>
        )}
      </header>

      {modoReserva ? (
        <div className="reserva-vista-reserva">
          <MiReservaVista id={idReserva} token={token} />
        </div>
      ) : (
        <>
          <section className="reserva-intro">
            <p className="page-eyebrow">TU NOCHE EMPIEZA AQUÍ</p>
            <h1>Reserva tu espacio.</h1>
            <p>Cuéntanos qué estás buscando y nuestro equipo te ayudará a confirmarlo.</p>
          </section>
          <ChatAsistente
            eventoInicialId={Number.isInteger(eventoId) && eventoId > 0 ? eventoId : null}
            promotorId={Number.isInteger(promotorId) && promotorId > 0 ? promotorId : null}
          />
        </>
      )}

      <footer className="reserva-publica-footer">Medallo Club · Medellín, Colombia</footer>
    </main>
  );
}
