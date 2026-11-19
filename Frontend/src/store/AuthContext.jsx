import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { login as loginRequest } from "../services/authService";
import { guardarToken, limpiarToken, obtenerToken } from "../services/apiClient";

const AuthContext = createContext(null);

const SESSION_STORAGE_KEY = "nightlife_ds_session";

function leerSesionGuardada() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(() => leerSesionGuardada());
  const [cargando, setCargando] = useState(false);

  useEffect(() => {
    if (usuario) {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(usuario));
    } else {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    }
  }, [usuario]);

  async function iniciarSesion(email, password) {
    setCargando(true);
    try {
      const respuesta = await loginRequest(email, password);
      guardarToken(respuesta.access_token);
      const sesion = {
        id: respuesta.usuario_id,
        nombre: respuesta.nombre,
        rol: respuesta.rol,
      };
      setUsuario(sesion);
      return sesion;
    } finally {
      setCargando(false);
    }
  }

  function cerrarSesion() {
    limpiarToken();
    setUsuario(null);
  }

  const value = useMemo(
    () => ({
      usuario,
      estaAutenticado: Boolean(usuario && obtenerToken()),
      cargando,
      iniciarSesion,
      cerrarSesion,
    }),
    [usuario, cargando]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth debe usarse dentro de un AuthProvider");
  }
  return context;
}
