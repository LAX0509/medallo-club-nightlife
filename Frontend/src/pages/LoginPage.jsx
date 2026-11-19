import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../store/AuthContext";
import { mensajeDeError } from "../services/apiClient";
import { RUTA_INICIO_POR_ROL } from "../utils/roles";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import "./LoginPage.css";

export function LoginPage() {
  const { iniciarSesion, estaAutenticado, usuario, cargando } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState(location.state?.email ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(location.state?.registroExitoso ? "Cuenta creada. Ya puedes iniciar sesión." : null);

  if (estaAutenticado) {
    return <Navigate to={RUTA_INICIO_POR_ROL[usuario.rol] ?? "/"} replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    try {
      const sesion = await iniciarSesion(email, password);
      navigate(RUTA_INICIO_POR_ROL[sesion.rol] ?? "/", { replace: true });
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible iniciar sesión"));
    }
  }

  return (
    <main className="login-page">
      <section className="login-aside" aria-label="Medallo Club">
        <div className="login-aside-brand"><img className="login-brand-seal" src={medalloLogo} alt="" /><span><strong>MEDALLO CLUB</strong><small>Provenza · Medellín</small></span></div>
        <div className="login-editorial">
          <p className="login-kicker">OPERACIÓN NOCTURNA</p>
          <h2>La noche,<br /><em>bajo control.</em></h2>
          <p>Accesos, invitados y resultados en un solo lugar.</p>
        </div>
        <span className="login-aside-foot">MEDELLÍN · COLOMBIA</span>
      </section>

      <section className="login-main">
        <form className="login-card" onSubmit={handleSubmit}>
          <Link className="login-home-cta" to="/">← Volver al inicio</Link>
          <div className="login-card-heading"><p className="page-eyebrow">ACCESO PRIVADO</p><h1>Bienvenido</h1><p>Ingresa con tu cuenta para continuar.</p></div>
      {error && <div className="alert-banner nivel-alto" role="alert">{error}</div>}
          {notice && <div className="register-success" role="status">{notice}</div>}

          <div className="form-field">
            <label htmlFor="email">Correo electrónico</label>
            <input id="email" type="email" placeholder="nombre@medalloclub.com" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>

          <div className="form-field">
            <label htmlFor="password">Contraseña</label>
            <input id="password" type="password" placeholder="Ingresa tu contraseña" required autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>

          <button className="btn btn-primary btn-block login-submit" type="submit" disabled={cargando}>
            {cargando ? "Ingresando..." : "Iniciar sesión"}
            {!cargando && <span aria-hidden="true">→</span>}
          </button>
          <p className="login-footnote">Acceso exclusivo para el equipo autorizado.</p>
          <Link className="login-register-cta" to="/registro">
            ¿Eres promotor? <strong>Crear cuenta</strong>
          </Link>
          <Link className="reservation-cta" to="/reservas">
            ¿Vienes al evento? Solicita una mesa o un palco <span aria-hidden="true">→</span>
          </Link>
        </form>
        <span className="login-copyright">© Medallo Club</span>
      </section>
    </main>
  );
}
