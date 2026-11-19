import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import { useAuth } from "../store/AuthContext";
import { NotificationBell } from "./NotificationBell";
import { ROLES } from "../utils/roles";
import "./AppLayout.css";

const ENLACES_POR_ROL = {
  [ROLES.ADMINISTRADOR]: [
    { to: "/dashboard", label: "Panel general", icon: "grid" },
    { to: "/escaner", label: "Control de acceso", icon: "scan" },
    { to: "/listas", label: "Invitados y comisiones", icon: "users" },
    { to: "/reservas-admin", label: "Solicitudes de reserva", icon: "calendar" },
    { to: "/agenda", label: "Agenda y flyers", icon: "calendar" },
    { to: "/inventario", label: "Inventario", icon: "inventory" },
    { to: "/sentimientos", label: "Sentimientos", icon: "sentiment" },
    { to: "/bot", label: "Asistente y WhatsApp", icon: "bot" },
    { to: "/usuarios", label: "Equipo", icon: "team" },
  ],
  [ROLES.PROMOTOR]: [
    { to: "/promotor/resumen", label: "Resumen", icon: "grid" },
    { to: "/promotor/invitados", label: "Mis invitados", icon: "users" },
    { to: "/promotor/reservas", label: "Mis reservas", icon: "calendar" },
    { to: "/promotor/comisiones", label: "Mis comisiones", icon: "cash" },
    { to: "/promotor/eventos", label: "Eventos y material", icon: "image" },
  ],
  [ROLES.PUERTA]: [
    { to: "/escaner", label: "Escáner QR", icon: "scan" },
    { to: "/escaner/buscar", label: "Buscar invitado", icon: "users" },
    { to: "/escaner/historial", label: "Historial e incidencias", icon: "calendar" },
  ],
};

const ICONOS = {
  home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v12h14V9M9 21v-7h6v7"/></>,
  inventory: <><path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3.3 8 8.7 5 8.7-5M12 13v8"/><path d="M7.5 5.5 16.5 11"/></>,
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.4"/><rect x="14" y="3" width="7" height="7" rx="1.4"/><rect x="3" y="14" width="7" height="7" rx="1.4"/><rect x="14" y="14" width="7" height="7" rx="1.4"/></>,
  scan: <><path d="M7 3H5a2 2 0 0 0-2 2v2M17 3h2a2 2 0 0 1 2 2v2M21 17v2a2 2 0 0 1-2 2h-2M3 17v2a2 2 0 0 0 2 2h2"/><path d="M7 12h10M12 7v10"/></>,
  users: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
  team: <><circle cx="12" cy="8" r="4"/><path d="M5 21a7 7 0 0 1 14 0M19 8h3M20.5 6.5v3"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/><path d="m9 16 2 2 4-4"/></>,
  cash: <><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M7 9h.01M17 15h.01"/></>,
  image: <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></>,
  sentiment: <><circle cx="12" cy="12" r="9"/><path d="M8 14s1.5 2 4 2 4-2 4-2M9 9h.01M15 9h.01"/></>,
  bot: <><rect x="4" y="8" width="16" height="11" rx="3"/><path d="M12 8V4M9 13h.01M15 13h.01M9.5 16.5h5"/><circle cx="12" cy="3.5" r="1"/></>,
};

function Icon({ name }) {
  return <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{ICONOS[name]}</svg>;
}

export function AppLayout() {
  const { usuario, cerrarSesion } = useAuth();
  const location = useLocation();
  const enlaces = ENLACES_POR_ROL[usuario?.rol] ?? [];
  const rutaActual = enlaces.find((enlace) => location.pathname === enlace.to);
  const iniciales = usuario?.nombre?.split(" ").filter(Boolean).slice(0, 2).map((parte) => parte[0]).join("").toUpperCase() || "MC";

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <Link className="app-brand" to="/" aria-label="Medallo Club, inicio">
          <img className="app-brand-mark" src={medalloLogo} alt="" />
          <span className="app-brand-copy"><strong>MEDALLO CLUB</strong><small>Provenza · Medellín</small></span>
        </Link>

        <Link className="app-home-link" to="/">
          <Icon name="home" /><span>Volver al inicio</span>
        </Link>

        <div className="app-nav-label">OPERACIÓN</div>
        <nav className="app-nav" aria-label="Navegación principal">
          {enlaces.map((enlace) => (
            <NavLink key={enlace.to} to={enlace.to} end className={({ isActive }) => `app-nav-link${isActive ? " active" : ""}`}>
              <Icon name={enlace.icon} /><span>{enlace.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="app-sidebar-note"><span className="status-dot" />Turno activo</div>
        <div className="app-user">
          <div className="app-user-avatar">{iniciales}</div>
          <div className="app-user-info"><strong className="app-user-name">{usuario?.nombre}</strong><span className="app-user-rol">{usuario?.rol}</span></div>
          <button className="app-logout" onClick={cerrarSesion} aria-label="Cerrar sesión" title="Cerrar sesión">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg>
          </button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <div className="app-breadcrumb"><span>MEDALLO CLUB</span><span className="breadcrumb-separator">/</span><strong>{rutaActual?.label ?? "Operación"}</strong></div>
          <div className="app-topbar-actions">
            <NotificationBell />
            <div className="app-topbar-status"><span className="status-dot" />Sistema operativo</div>
          </div>
        </header>
        <main className="app-content"><Outlet /></main>
      </div>
    </div>
  );
}
