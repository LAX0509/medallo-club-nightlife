import { Navigate } from "react-router-dom";
import { useAuth } from "../store/AuthContext";

export function ProtectedRoute({ rolesPermitidos, children }) {
  const { usuario, estaAutenticado } = useAuth();

  if (!estaAutenticado) {
    return <Navigate to="/login" replace />;
  }

  if (rolesPermitidos && !rolesPermitidos.includes(usuario.rol)) {
    return <Navigate to="/" replace />;
  }

  return children;
}
