import { useEffect, useState } from "react";
import { useAuth } from "../store/AuthContext";
import { listarEventos, esVideoEvento, urlFlyerEvento } from "../services/eventosService";
import { mensajeDeError } from "../services/apiClient";
import { AlertBanner } from "../components/AlertBanner";
import "./PromotorPages.css";

function fechaLarga(fecha) {
  return new Date(`${fecha}T12:00:00`).toLocaleDateString("es-CO", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

function enlaceCompartir(evento, promotorId) {
  const url = new URL("/reservas", window.location.origin);
  url.searchParams.set("promotor", String(promotorId));
  url.searchParams.set("evento", String(evento.id));
  const texto = `¡Vamos a ${evento.nombre} en Medallo Club!${evento.tematica ? ` ${evento.tematica}.` : ""} Solicita tu mesa o palco aquí: ${url.toString()}`;
  return `https://wa.me/?text=${encodeURIComponent(texto)}`;
}

export function PromotorEventosPage() {
  const { usuario } = useAuth();
  const [eventos, setEventos] = useState([]);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    listarEventos({ limit: 100 })
      .then((respuesta) => setEventos(respuesta.items.filter((evento) => evento.estado === "planeado" && evento.fecha >= new Date().toISOString().slice(0, 10))))
      .catch((err) => setError(mensajeDeError(err, "No fue posible cargar los eventos.")))
      .finally(() => setCargando(false));
  }, []);

  return (
    <div className="promotor-page">
      <div className="page-header"><div className="page-heading"><p className="page-eyebrow">AGENDA DEL CLUB</p><h1>Eventos y material</h1><p className="page-subtitle">Consulta la próxima programación y comparte tu enlace personal de reservas.</p></div></div>
      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {cargando ? <p className="promotor-vacio">Cargando agenda…</p> : eventos.length === 0 ? <section className="card promotor-vacio"><strong>No hay próximos eventos publicados</strong><p>Cuando administración publique una fecha, aparecerá aquí con su flyer y enlace para compartir.</p></section> : (
        <div className="promotor-eventos-grid">{eventos.map((evento) => (
          <article className="card promotor-evento-card" key={evento.id}>
            {evento.flyer_url && (esVideoEvento(evento.flyer_url) ? <video className="promotor-evento-media" src={urlFlyerEvento(evento.flyer_url)} muted loop playsInline autoPlay preload="metadata" /> : <img className="promotor-evento-media" src={urlFlyerEvento(evento.flyer_url)} alt={`Flyer de ${evento.nombre}`} />)}
            <div className="promotor-evento-copy"><p className="section-kicker">{fechaLarga(evento.fecha)}</p><h2>{evento.nombre}</h2>{evento.tematica && <p>{evento.tematica}</p>}<a className="btn btn-primary" href={enlaceCompartir(evento, usuario.id)} target="_blank" rel="noreferrer">Compartir por WhatsApp ↗</a></div>
          </article>
        ))}</div>
      )}
    </div>
  );
}
