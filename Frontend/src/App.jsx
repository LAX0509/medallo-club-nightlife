import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { PublicHomePage } from "./pages/PublicHomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { DashboardPage } from "./pages/DashboardPage";
import { EscanerPage } from "./pages/EscanerPage";
import { ListasComisionesPage } from "./pages/ListasComisionesPage";
import { UsuariosPage } from "./pages/UsuariosPage";
import { ReservaChatPage } from "./pages/ReservaChatPage";
import { ReservasAdminPage } from "./pages/ReservasAdminPage";
import { AgendaAdminPage } from "./pages/AgendaAdminPage";
import { PromotorEventosPage } from "./pages/PromotorEventosPage";
import { InventarioPage } from "./pages/InventarioPage";
import { SentimientosPage } from "./pages/SentimientosPage";
import { PromotorReservasPage } from "./pages/PromotorReservasPage";
import { PasePublicoPage } from "./pages/PasePublicoPage";
import { PrivacidadPage } from "./pages/PrivacidadPage";
import { BotPage } from "./pages/BotPage";
import { useAuth } from "./store/AuthContext";
import { ROLES } from "./utils/roles";

function InicioListasPorRol() {
  const { usuario } = useAuth();
  if (usuario.rol === ROLES.PROMOTOR) return <Navigate to="/promotor/resumen" replace />;
  return <ListasComisionesPage />;
}
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<PublicHomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/registro" element={<RegisterPage />} />
      <Route path="/reservas" element={<ReservaChatPage />} />
      <Route path="/pase/:codigo" element={<PasePublicoPage />} />
      <Route path="/privacidad" element={<PrivacidadPage />} />

      <Route
        element={
          <ProtectedRoute>
            <AppLayout />
          </ProtectedRoute>
        }
      >
        <Route
          path="dashboard"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}>
              <DashboardPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="escaner"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR, ROLES.PUERTA]}>
              <EscanerPage vista="escaner" />
            </ProtectedRoute>
          }
        />

        <Route path="escaner/buscar" element={<ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR, ROLES.PUERTA]}><EscanerPage vista="buscar" /></ProtectedRoute>} />
        <Route path="escaner/historial" element={<ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR, ROLES.PUERTA]}><EscanerPage vista="historial" /></ProtectedRoute>} />

        <Route path="listas" element={<ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR, ROLES.PROMOTOR]}><InicioListasPorRol /></ProtectedRoute>} />
        <Route path="promotor/resumen" element={<ProtectedRoute rolesPermitidos={[ROLES.PROMOTOR]}><ListasComisionesPage seccion="resumen" /></ProtectedRoute>} />
        <Route path="promotor/invitados" element={<ProtectedRoute rolesPermitidos={[ROLES.PROMOTOR]}><ListasComisionesPage seccion="invitados" /></ProtectedRoute>} />
        <Route path="promotor/comisiones" element={<ProtectedRoute rolesPermitidos={[ROLES.PROMOTOR]}><ListasComisionesPage seccion="comisiones" /></ProtectedRoute>} />
        <Route path="promotor/reservas" element={<ProtectedRoute rolesPermitidos={[ROLES.PROMOTOR]}><PromotorReservasPage /></ProtectedRoute>} />
        <Route path="promotor/eventos" element={<ProtectedRoute rolesPermitidos={[ROLES.PROMOTOR]}><PromotorEventosPage /></ProtectedRoute>} />

        <Route path="sentimientos" element={<ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}><SentimientosPage /></ProtectedRoute>} />
        <Route path="bot" element={<ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}><BotPage /></ProtectedRoute>} />

        <Route
          path="usuarios"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}>
              <UsuariosPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="inventario"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}>
              <InventarioPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="agenda"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}>
              <AgendaAdminPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="reservas-admin"
          element={
            <ProtectedRoute rolesPermitidos={[ROLES.ADMINISTRADOR]}>
              <ReservasAdminPage />
            </ProtectedRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
