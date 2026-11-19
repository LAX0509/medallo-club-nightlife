import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import {
  listarNotificaciones,
  marcarNotificacionLeida,
  marcarTodasLeidas,
} from "../services/notificacionesService";
import "./NotificationBell.css";

const INTERVALO_SONDEO_MS = 30000;
const DURACION_TOAST_MS = 6000;
const MAX_ITEMS = 20;

function fechaUtc(valor) {
  if (!valor) return null;
  const texto = String(valor);
  // Si el servidor entrega la fecha sin zona horaria, se interpreta como UTC.
  const fecha = new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(texto) ? texto : `${texto}Z`);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

function tiempoRelativo(valor, ahora = Date.now()) {
  const fecha = fechaUtc(valor);
  if (!fecha) return "";
  const segundos = Math.max(0, Math.round((ahora - fecha.getTime()) / 1000));
  if (segundos < 60) return "hace un momento";
  const minutos = Math.floor(segundos / 60);
  if (minutos < 60) return `hace ${minutos} min`;
  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `hace ${horas} h`;
  const dias = Math.floor(horas / 24);
  if (dias < 7) return `hace ${dias} ${dias === 1 ? "día" : "días"}`;
  return fecha.toLocaleDateString("es-CO", { day: "numeric", month: "short" });
}

function IconoCampana() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M6 9a6 6 0 0 1 12 0c0 6 2.5 7.5 2.5 7.5h-17S6 15 6 9Z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </svg>
  );
}

export function NotificationBell() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [noLeidas, setNoLeidas] = useState(0);
  const [abierto, setAbierto] = useState(false);
  const [cargado, setCargado] = useState(false);
  const [fallo, setFallo] = useState(false);
  const [toast, setToast] = useState(null);
  const [ahora, setAhora] = useState(() => Date.now());
  const contenedorRef = useRef(null);
  const botonRef = useRef(null);
  const previoNoLeidas = useRef(null);
  const temporizadorToast = useRef(null);
  const montado = useRef(true);

  const cerrarToast = useCallback(() => {
    window.clearTimeout(temporizadorToast.current);
    temporizadorToast.current = null;
    setToast(null);
  }, []);

  const mostrarToast = useCallback((notificacion) => {
    window.clearTimeout(temporizadorToast.current);
    setToast({ id: notificacion.id, titulo: notificacion.titulo, nivel: notificacion.nivel });
    temporizadorToast.current = window.setTimeout(() => {
      temporizadorToast.current = null;
      setToast(null);
    }, DURACION_TOAST_MS);
  }, []);

  const cargar = useCallback(async () => {
    try {
      const data = await listarNotificaciones({ limite: MAX_ITEMS });
      if (!montado.current) return;
      const lista = Array.isArray(data.items) ? data.items.slice(0, MAX_ITEMS) : [];
      const total = Number(data.no_leidas) || 0;
      const previo = previoNoLeidas.current;
      if (previo !== null && total > previo) {
        const reciente = lista.find((item) => !item.leida);
        if (reciente && (reciente.nivel === "alerta" || reciente.nivel === "critica")) {
          mostrarToast(reciente);
        }
      }
      previoNoLeidas.current = total;
      setItems(lista);
      setNoLeidas(total);
      setAhora(Date.now());
      setFallo(false);
    } catch {
      if (montado.current) setFallo(true);
    } finally {
      if (montado.current) setCargado(true);
    }
  }, [mostrarToast]);

  useEffect(() => {
    montado.current = true;
    cargar();
    const intervalo = window.setInterval(cargar, INTERVALO_SONDEO_MS);
    function alCambiarVisibilidad() {
      if (document.visibilityState === "visible") cargar();
    }
    document.addEventListener("visibilitychange", alCambiarVisibilidad);
    return () => {
      montado.current = false;
      window.clearInterval(intervalo);
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
      window.clearTimeout(temporizadorToast.current);
    };
  }, [cargar]);

  useEffect(() => {
    if (!abierto) return undefined;
    function clicFuera(event) {
      if (contenedorRef.current && !contenedorRef.current.contains(event.target)) setAbierto(false);
    }
    function teclado(event) {
      if (event.key === "Escape") {
        setAbierto(false);
        botonRef.current?.focus();
      }
    }
    document.addEventListener("mousedown", clicFuera);
    document.addEventListener("touchstart", clicFuera);
    document.addEventListener("keydown", teclado);
    return () => {
      document.removeEventListener("mousedown", clicFuera);
      document.removeEventListener("touchstart", clicFuera);
      document.removeEventListener("keydown", teclado);
    };
  }, [abierto]);

  function alternarPanel() {
    setAbierto((actual) => !actual);
    setAhora(Date.now());
  }

  async function abrirNotificacion(item) {
    setAbierto(false);
    if (!item.leida) {
      setItems((actuales) => actuales.map((n) => (n.id === item.id ? { ...n, leida: true } : n)));
      setNoLeidas((actual) => {
        const nuevo = Math.max(0, actual - 1);
        previoNoLeidas.current = nuevo;
        return nuevo;
      });
      try {
        await marcarNotificacionLeida(item.id);
      } catch {
        cargar();
      }
    }
    if (item.enlace) navigate(item.enlace);
  }

  async function leerTodas() {
    setItems((actuales) => actuales.map((n) => ({ ...n, leida: true })));
    setNoLeidas(0);
    previoNoLeidas.current = 0;
    try {
      await marcarTodasLeidas();
    } catch {
      cargar();
    }
  }

  const insignia = noLeidas > 99 ? "99+" : String(noLeidas);
  const etiqueta = noLeidas > 0
    ? `Notificaciones: ${noLeidas} sin leer`
    : "Notificaciones";

  return (
    <div className="notif-bell" ref={contenedorRef}>
      <button
        ref={botonRef}
        className={`notif-bell-button${abierto ? " is-open" : ""}`}
        type="button"
        onClick={alternarPanel}
        aria-label={etiqueta}
        aria-expanded={abierto}
        aria-haspopup="true"
        aria-controls="notif-bell-panel"
      >
        <IconoCampana />
        {noLeidas > 0 && <span className="notif-bell-badge" aria-hidden="true">{insignia}</span>}
      </button>

      {abierto && (
        <section className="notif-panel" id="notif-bell-panel" aria-label="Notificaciones">
          <header className="notif-panel-header">
            <h2>Notificaciones</h2>
            <button className="notif-panel-readall" type="button" onClick={leerTodas} disabled={noLeidas === 0}>
              Marcar todas como leídas
            </button>
          </header>
          {!cargado ? (
            <p className="notif-panel-empty">Cargando…</p>
          ) : fallo && items.length === 0 ? (
            <p className="notif-panel-empty">No fue posible cargar las notificaciones.</p>
          ) : items.length === 0 ? (
            <p className="notif-panel-empty">Estás al día</p>
          ) : (
            <ul className="notif-list">
              {items.map((item) => (
                <li key={item.id}>
                  <button
                    className={`notif-item nivel-${item.nivel}${item.leida ? "" : " is-unread"}`}
                    type="button"
                    onClick={() => abrirNotificacion(item)}
                  >
                    <span className="notif-dot" aria-hidden="true" />
                    <span className="notif-item-body">
                      <span className="notif-item-title">
                        {!item.leida && <span className="notif-sr">Sin leer: </span>}
                        {item.titulo}
                      </span>
                      <span className="notif-item-message">{item.mensaje}</span>
                      <time className="notif-item-time" dateTime={item.creada_en}>{tiempoRelativo(item.creada_en, ahora)}</time>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {createPortal(
        <div className="notif-toast-region" role="status">
          {toast && (
            <div className={`notif-toast nivel-${toast.nivel}`}>
              <span className="notif-dot" aria-hidden="true" />
              <div className="notif-toast-body">
                <strong>{toast.titulo}</strong>
                <span>Nueva notificación</span>
              </div>
              <button className="notif-toast-close" type="button" onClick={cerrarToast} aria-label="Cerrar aviso">×</button>
            </div>
          )}
        </div>,
        document.body,
      )}
    </div>
  );
}
