import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { AlertBanner } from "../components/AlertBanner";
import { listarUsuarios, crearUsuario, actualizarUsuario } from "../services/usuariosService";
import { mensajeDeError } from "../services/apiClient";
import "./UsuariosPage.css";

const ROLES_DISPONIBLES = ["Administrador", "Promotor", "Puerta"];

const FORM_INICIAL = { nombre: "", email: "", password: "", rol: "Promotor", telefono: "" };

export function UsuariosPage() {
  const [usuarios, setUsuarios] = useState([]);
  const [error, setError] = useState(null);
  const [exito, setExito] = useState(null);
  const [form, setForm] = useState(FORM_INICIAL);

  async function recargar() {
    try {
      const data = await listarUsuarios({ limit: 100 });
      setUsuarios(data.items);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar los usuarios"));
    }
  }

  useEffect(() => {
    recargar();
  }, []);

  async function handleCrear(event) {
    event.preventDefault();
    setError(null);
    setExito(null);
    try {
      await crearUsuario(form);
      setForm(FORM_INICIAL);
      setExito("Usuario creado correctamente.");
      recargar();
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible crear el usuario"));
    }
  }

  async function handleCambiarRol(usuarioId, rol) {
    await actualizarUsuario(usuarioId, { rol });
    recargar();
  }

  async function handleCambiarEstado(usuarioId, estado) {
    await actualizarUsuario(usuarioId, { estado });
    recargar();
  }

  return (
    <div>
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">ADMINISTRACIÓN</p>
          <h1>Equipo y permisos</h1>
          <p className="page-subtitle">Gestiona accesos y responsabilidades del equipo.</p>
        </div>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {exito && <AlertBanner nivel="bajo">{exito}</AlertBanner>}

      <div className="usuarios-grid">
        <div className="card">
          <div className="section-heading"><div><p className="section-kicker">PERSONAL AUTORIZADO</p><h2>Usuarios registrados</h2></div><span className="table-count">{usuarios.length}</span></div>
          <div className="table-scroll"><table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Correo</th>
                <th>Rol</th>
                <th>Estado</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {usuarios.map((u) => (
                <tr key={u.id}>
                  <td>{u.nombre}</td>
                  <td>{u.email}</td>
                  <td>
                    <select value={u.rol} onChange={(e) => handleCambiarRol(u.id, e.target.value)}>
                      {ROLES_DISPONIBLES.map((rol) => (
                        <option key={rol} value={rol}>
                          {rol}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <Badge variante={u.estado ? "success" : "neutral"}>{u.estado ? "Activo" : "Inactivo"}</Badge>
                  </td>
                  <td>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleCambiarEstado(u.id, !u.estado)}
                    >
                      {u.estado ? "Desactivar" : "Activar"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </div>

        <div className="card">
          <p className="section-kicker">NUEVO ACCESO</p>
          <h2>Crear usuario</h2>
          <form onSubmit={handleCrear}>
            <div className="form-field">
              <label htmlFor="nombre">Nombre</label>
              <input
                id="nombre"
                required
                value={form.nombre}
                onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))}
              />
            </div>
            <div className="form-field">
              <label htmlFor="email">Correo</label>
              <input
                id="email"
                type="email"
                required
                value={form.email}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              />
            </div>
            <div className="form-field">
              <label htmlFor="password">Contraseña temporal</label>
              <input
                id="password"
                type="password"
                required
                minLength={8}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
              <span className="field-hint">Mínimo 8 caracteres, con al menos un número.</span>
            </div>
            <div className="form-field">
              <label htmlFor="rol">Rol</label>
              <select
                id="rol"
                value={form.rol}
                onChange={(e) => setForm((f) => ({ ...f, rol: e.target.value }))}
              >
                {ROLES_DISPONIBLES.map((rol) => (
                  <option key={rol} value={rol}>
                    {rol}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-field">
              <label htmlFor="telefono">Teléfono (opcional)</label>
              <input
                id="telefono"
                value={form.telefono}
                onChange={(e) => setForm((f) => ({ ...f, telefono: e.target.value }))}
              />
            </div>
            <button className="btn btn-primary btn-block" type="submit">
              Crear usuario
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
