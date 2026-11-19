import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listarEventosParaReservas } from "../services/reservasService";
import { esVideoEvento, urlFlyerEvento } from "../services/eventosService";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import medalloFachada from "../assets/medallo-brand/medallo-fachada.png";
import "./PublicHomePage.css";

function fechaEvento(fecha) {
  const valor = new Date(`${fecha}T12:00:00`);
  return {
    dia: new Intl.DateTimeFormat("es-CO", { day: "2-digit" }).format(valor),
    mes: new Intl.DateTimeFormat("es-CO", { month: "short" }).format(valor).replace(".", "").toUpperCase(),
    diaSemana: new Intl.DateTimeFormat("es-CO", { weekday: "long" }).format(valor),
  };
}

export function PublicHomePage() {
  const [eventos, setEventos] = useState([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    listarEventosParaReservas()
      .then(setEventos)
      .catch(() => setEventos([]))
      .finally(() => setCargando(false));
  }, []);

  return (
    <main className="public-home">
      <header className="home-nav">
        <Link className="home-brand" to="/" aria-label="Medallo Club, inicio">
          <img className="home-brand-logo" src={medalloLogo} alt="" />
          <span className="home-brand-name"><b>PROVENZA</b><small>MEDELLÍN · COLOMBIA</small></span>
        </Link>
        <nav className="home-nav-links" aria-label="Navegación pública">
          <a href="#agenda">Agenda</a>
          <a href="#experiencia">La experiencia</a>
          <a href="#ubicacion">Ubicación</a>
        </nav>
        <div className="home-nav-actions">
          <Link className="home-login" to="/login">Equipo</Link>
        </div>
      </header>

      <section className="home-hero">
        <div className="home-hero-grain" aria-hidden="true" />
        <div className="home-hero-copy">
          <p className="home-eyebrow"><span /> PROVENZA · MEDELLÍN</p>
          <h1>La noche<br />tiene su <em>lugar.</em></h1>
          <p className="home-hero-description">Música urbana, luces y el pulso de Provenza en un lugar hecho para encontrarse.</p>
          <div className="home-hero-actions">
            <a className="home-button" href="#agenda">Explorar la agenda <span aria-hidden="true">↓</span></a>
          </div>
          <p className="home-hero-motto">DEL BARRIO <span>PA’ LA FAMA</span></p>
        </div>
        <div className="home-hero-art" aria-hidden="true">
          <div className="home-photo-frame">
            <img className="home-facade-photo" src={medalloFachada} alt="Fachada iluminada de Medallo Club en Provenza" />
            <div className="home-photo-shade" />
            <div className="home-photo-caption"><span>LA NOCHE</span><i /><span>ES NUESTRA</span></div>
          </div>
          <span className="home-photo-index">MC / 001</span>
        </div>
        <a className="home-scroll" href="#agenda"><span /> DESLIZA PARA EXPLORAR</a>
      </section>

      <section id="agenda" className="home-agenda">
        <div className="home-section-heading">
          <div><p className="home-eyebrow">EN EL CLUB</p><h2>Agenda</h2></div>
        </div>
        {cargando ? <p className="home-empty">Cargando agenda…</p> : eventos.length === 0 ? (
          <div className="home-empty-card"><span>La próxima fecha se está preparando.</span><p>Vuelve pronto para conocer la programación.</p></div>
        ) : (
          <div className="home-event-grid">
            {eventos.slice(0, 6).map((evento, index) => {
              const fecha = fechaEvento(evento.fecha);
              return (
                <article className={`home-event-card home-event-card-${index % 3}${evento.flyer_url ? " has-flyer" : ""}`} key={evento.id}>
                  {evento.flyer_url && (esVideoEvento(evento.flyer_url) ? <video className="home-event-flyer" src={urlFlyerEvento(evento.flyer_url)} muted loop playsInline autoPlay preload="metadata" aria-hidden="true" /> : <img className="home-event-flyer" src={urlFlyerEvento(evento.flyer_url)} alt={`Flyer de ${evento.nombre}`} />)}
                  <div className="home-event-date"><strong>{fecha.dia}</strong><span>{fecha.mes}</span></div>
                  <div className="home-event-info"><p>{evento.tematica || fecha.diaSemana}</p><h3>{evento.nombre}</h3></div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section id="experiencia" className="home-experience">
        <div className="home-experience-label"><p className="home-eyebrow">IDENTIDAD DE BARRIO</p><span>001 / MEDELLÍN</span></div>
        <div className="home-experience-copy"><h2>De Provenza<br />pa’l mundo.</h2><p>Raíces paisas, identidad de barrio y una programación urbana que cambia con cada noche.</p><div className="home-genres"><span>REGGAETÓN</span><i /> <span>TRAP</span><i /> <span>HIP HOP</span><i /> <span>DEMBOW</span></div></div>
        <div className="home-experience-mark" aria-hidden="true">MC</div>
      </section>

      <section className="home-reserve-strip">
        <p className="home-eyebrow">PLAN EN GRUPO</p>
        <h2>¿Mesa o palco?</h2>
        <p className="home-reserve-copy">Cuéntanos cuántos vienen y qué espacio buscan. El equipo revisará la disponibilidad del evento.</p>
        <Link className="home-button" to="/reservas">Solicitar mesa o palco <span aria-hidden="true">↗</span></Link>
        <small>La solicitud queda pendiente hasta recibir confirmación del club.</small>
      </section>

      <footer id="ubicacion" className="home-footer">
        <Link className="home-brand" to="/" aria-label="Medallo Club, inicio"><img className="home-brand-logo" src={medalloLogo} alt="" /><span className="home-brand-name"><small>DEL BARRIO PA’ LA FAMA</small></span></Link>
        <div className="home-footer-location"><span>ENCUÉNTRANOS</span><p>Cra. 35 #7-21, El Poblado<br />Medellín, Antioquia</p><a href="https://www.google.com/maps/place/MEDALLO+CLUB/@6.2063786,-75.5681385,17z" target="_blank" rel="noreferrer">Abrir en mapas ↗</a></div>
        <div className="home-footer-social"><span>SÍGUENOS</span><a href="https://www.instagram.com/medalloclub.mde/?hl=es" target="_blank" rel="noreferrer">Instagram ↗</a><small>Ingreso exclusivo para mayores de 18 años.</small></div>
        <div className="home-footer-bottom"><span>© MEDALLO CLUB · MEDELLÍN</span><span><Link to="/privacidad">Política de privacidad</Link> · <Link to="/login">Acceso del equipo</Link></span></div>
      </footer>
    </main>
  );
}
