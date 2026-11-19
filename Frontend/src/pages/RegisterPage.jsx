import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { mensajeDeError } from "../services/apiClient";
import { registrarPromotor } from "../services/authService";
import medalloLogo from "../assets/medallo-brand/medallo-logo-ui.png";
import "./LoginPage.css";

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ nombre: "", email: "", telefono: "", password: "", confirmar: "" });
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  function cambiar(campo, valor) {
    setForm((actual) => ({ ...actual, [campo]: valor }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    if (form.password !== form.confirmar) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setEnviando(true);
    try {
      await registrarPromotor({
        nombre: form.nombre.trim(),
        email: form.email.trim().toLowerCase(),
        telefono: form.telefono.trim() || null,
        password: form.password,
      });
      navigate("/login", { replace: true, state: { registroExitoso: true, email: form.email.trim().toLowerCase() } });
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible crear la cuenta. Intenta de nuevo."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-aside" aria-label="Medallo Club">
        <div className="login-aside-brand"><img className="login-brand-seal" src={medalloLogo} alt="" /><span><strong>MEDALLO CLUB</strong><small>Provenza · Medellín</small></span></div>
        <div className="login-editorial">
          <p className="login-kicker">ÚNETE AL EQUIPO</p>
          <h2>Tu gente,<br /><em>tu noche.</em></h2>
          <p>Registra invitados y sigue el rendimiento de tus listas.</p>
        </div>
        <span className="login-aside-foot">MEDELLÍN · COLOMBIA</span>
      </section>

      <section className="login-main">
        <form className="login-card register-card" onSubmit={handleSubmit}>
          <Link className="login-home-cta" to="/">← Volver al inicio</Link>
          <div className="login-card-heading"><p className="page-eyebrow">CUENTA DE PROMOTOR</p><h1>Crear cuenta</h1><p>Completa tus datos para gestionar tus invitados.</p></div>
          {error && <div className="alert-banner nivel-alto" role="alert">{error}</div>}

          <div className="form-field"><label htmlFor="registro-nombre">Nombre completo</label><input id="registro-nombre" autoComplete="name" maxLength={100} required value={form.nombre} onChange={(e) => cambiar("nombre", e.target.value)} /></div>
          <div className="form-field"><label htmlFor="registro-email">Correo electrónico</label><input id="registro-email" type="email" autoComplete="email" required value={form.email} onChange={(e) => cambiar("email", e.target.value)} /></div>
          <div className="form-field"><label htmlFor="registro-telefono">Teléfono <span>(opcional)</span></label><input id="registro-telefono" type="tel" autoComplete="tel" maxLength={20} value={form.telefono} onChange={(e) => cambiar("telefono", e.target.value)} /></div>
          <div className="form-field"><label htmlFor="registro-password">Contraseña</label><input id="registro-password" type="password" autoComplete="new-password" minLength={8} maxLength={72} required value={form.password} onChange={(e) => cambiar("password", e.target.value)} /><span className="field-hint">Mínimo 8 caracteres e incluye al menos un número.</span></div>
          <div className="form-field"><label htmlFor="registro-confirmar">Confirmar contraseña</label><input id="registro-confirmar" type="password" autoComplete="new-password" minLength={8} maxLength={72} required value={form.confirmar} onChange={(e) => cambiar("confirmar", e.target.value)} /></div>

          <button className="btn btn-primary btn-block login-submit" type="submit" disabled={enviando}>
            {enviando ? "Creando cuenta…" : "Registrarme"}
            {!enviando && <span aria-hidden="true">→</span>}
          </button>
          <p className="login-register-note">El registro crea una cuenta de promotor. Administradores y personal de puerta los registra un administrador.</p>
          <Link className="login-register-cta" to="/login">¿Ya tienes cuenta? <strong>Inicia sesión</strong></Link>
          <Link className="reservation-cta" to="/reservas">¿Vienes al evento? Solicita una mesa o un palco <span aria-hidden="true">→</span></Link>
        </form>
        <span className="login-copyright">© Medallo Club</span>
      </section>
    </main>
  );
}
