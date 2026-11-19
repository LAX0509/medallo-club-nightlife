import { useEffect, useState } from "react";
import { Badge } from "../components/Badge";
import { AlertBanner } from "../components/AlertBanner";
import { listarReservasReferidas } from "../services/reservasService";
import { mensajeDeError } from "../services/apiClient";
import "./PromotorPages.css";

const variantes = { pendiente: "accent", confirmada: "success", cancelada: "neutral" };

function fechaHora(fecha) {
  return new Date(fecha).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" });
}

export function PromotorReservasPage() {
  const [reservas, setReservas] = useState([]);
  const [error, setError] = useState(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    listarReservasReferidas()
      .then(setReservas)
      .catch((err) => setError(mensajeDeError(err, "No fue posible cargar tus reservas referidas.")))
      .finally(() => setCargando(false));
  }, []);

  const confirmadas = reservas.filter((reserva) => reserva.estado === "confirmada").length;
  const pasesUsados = reservas.reduce((suma, reserva) => suma + (reserva.estado === "confirmada" ? reserva.pases_usados ?? 0 : 0), 0);
  const pendientes = reservas.filter((reserva) => reserva.estado === "pendiente").length;

  return (
    <div className="promotor-page">
      <div className="page-header"><div className="page-heading"><p className="page-eyebrow">VENTAS REFERIDAS</p><h1>Mis reservas</h1><p className="page-subtitle">Solicitudes que llegaron al club desde tus enlaces de promotor.</p></div></div>
      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      <div className="promotor-resumen-grid">
        <article className="card promotor-resumen-card"><span>Solicitudes</span><strong>{reservas.length}</strong></article>
        <article className="card promotor-resumen-card"><span>Por revisar</span><strong>{pendientes}</strong></article>
        <article className="card promotor-resumen-card"><span>Garantizadas</span><strong>{confirmadas}</strong></article>
        <article className="card promotor-resumen-card"><span>Ingresos de tus referidos</span><strong>{pasesUsados}</strong></article>
      </div>
      <section className="card promotor-reservas-card">
        <div className="section-heading"><div><p className="section-kicker">MESAS Y PALCOS</p><h2>Actividad de tus enlaces</h2></div></div>
        {cargando ? <p className="promotor-vacio">Cargando tus reservas…</p> : reservas.length === 0 ? <div className="promotor-vacio"><strong>Aún no tienes reservas referidas</strong><p>Comparte el enlace de un evento desde “Eventos y material”. Las solicitudes que lleguen por ese enlace aparecerán aquí.</p></div> : (
          <div className="table-scroll"><table className="data-table promotor-reservas-tabla"><thead><tr><th>Cliente</th><th>Evento</th><th>Espacio</th><th>Grupo</th><th>Fecha de solicitud</th><th>Estado</th><th>Pases usados</th></tr></thead><tbody>{reservas.map((reserva) => {
            const garantizada = reserva.estado === "confirmada" && reserva.garantizada;
            const total = reserva.pases_total ?? 0;
            const usados = reserva.pases_usados ?? 0;
            return (
              <tr key={reserva.id}>
                <td><strong>{reserva.nombre_cliente}</strong><small>{reserva.telefono}</small></td>
                <td>{reserva.evento_nombre}</td>
                <td>{reserva.tipo === "mesa" ? "Mesa" : "Palco"}{garantizada && reserva.ubicacion_asignada && <small>{reserva.ubicacion_asignada}</small>}</td>
                <td>{reserva.asistentes}</td>
                <td>{fechaHora(reserva.fecha_solicitud)}</td>
                <td>
                  <Badge variante={variantes[reserva.estado] ?? "neutral"}>{garantizada ? "Garantizada" : reserva.estado}</Badge>
                  {garantizada && reserva.codigo_garantia && <code className="promotor-codigo-garantia">{reserva.codigo_garantia}</code>}
                  {garantizada && reserva.hora_limite && <small>Llegar antes de las {reserva.hora_limite}</small>}
                </td>
                <td>{garantizada && total > 0 ? (
                  <div className="promotor-pases">
                    <strong>{usados}/{total}</strong>
                    <div className="promotor-pases-barra" role="progressbar" aria-label="Pases usados" aria-valuemin={0} aria-valuemax={total} aria-valuenow={usados}><span style={{ width: `${Math.min(100, (usados / total) * 100)}%` }} /></div>
                  </div>
                ) : <span className="promotor-sin-pases">—</span>}</td>
              </tr>
            );
          })}</tbody></table></div>
        )}
      </section>
    </div>
  );
}
