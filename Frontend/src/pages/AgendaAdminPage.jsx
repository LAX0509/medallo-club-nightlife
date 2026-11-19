import { useEffect, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { mensajeDeError } from "../services/apiClient";
import {
  actualizarEvento,
  cargarFlyerEvento,
  crearEvento,
  eliminarEvento,
  eliminarFlyerEvento,
  esVideoEvento,
  listarEventos,
  urlFlyerEvento,
} from "../services/eventosService";
import { MAX_IMAGEN_ORIGINAL, MAX_VIDEO, prepararFlyer } from "../utils/imagenFlyer";
import "./AgendaAdminPage.css";

function fechaLocalHoy() {
  const ahora = new Date();
  ahora.setMinutes(ahora.getMinutes() - ahora.getTimezoneOffset());
  return ahora.toISOString().slice(0, 10);
}

function fechaLegible(fecha) {
  return new Date(`${fecha}T12:00:00`).toLocaleDateString("es-CO", {
    weekday: "long", day: "numeric", month: "long", year: "numeric",
  });
}

const formularioVacio = () => ({ nombre: "", fecha: fechaLocalHoy(), aforo_maximo: "300", tematica: "", estado: "planeado" });

export function AgendaAdminPage() {
  const [eventos, setEventos] = useState([]);
  const [formulario, setFormulario] = useState(formularioVacio);
  const [eventoEnEdicion, setEventoEnEdicion] = useState(null);
  const [archivo, setArchivo] = useState(null);
  const [vistaPrevia, setVistaPrevia] = useState("");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const [mensaje, setMensaje] = useState(null);
  const [progreso, setProgreso] = useState(null);

  async function cargarEventos() {
    setError(null);
    try {
      const respuesta = await listarEventos({ page: 1, limit: 100 });
      setEventos(respuesta.items);
    } catch (err) {
      setError(mensajeDeError(err, "No fue posible cargar la agenda."));
    } finally {
      setCargando(false);
    }
  }

  useEffect(() => { cargarEventos(); }, []);

  useEffect(() => {
    if (!archivo) {
      setVistaPrevia("");
      return undefined;
    }
    const url = URL.createObjectURL(archivo);
    setVistaPrevia(url);
    return () => URL.revokeObjectURL(url);
  }, [archivo]);

  function cambiarCampo(event) {
    setFormulario((actual) => ({ ...actual, [event.target.name]: event.target.value }));
  }

  function editar(evento) {
    setEventoEnEdicion(evento);
    setFormulario({
      nombre: evento.nombre,
      fecha: evento.fecha,
      aforo_maximo: String(evento.aforo_maximo),
      tematica: evento.tematica ?? "",
      estado: evento.estado,
    });
    setArchivo(null);
    setMensaje(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelarEdicion() {
    setEventoEnEdicion(null);
    setFormulario(formularioVacio());
    setArchivo(null);
    const entrada = document.getElementById("agenda-flyer");
    if (entrada) entrada.value = "";
  }

  async function guardar(event) {
    event.preventDefault();
    setGuardando(true);
    setError(null);
    setMensaje(null);
    try {
      const datos = {
        nombre: formulario.nombre.trim(),
        fecha: formulario.fecha,
        aforo_maximo: Number(formulario.aforo_maximo),
        tematica: formulario.tematica.trim() || null,
      };
      let guardado;
      if (eventoEnEdicion) {
        guardado = await actualizarEvento(eventoEnEdicion.id, { ...datos, tematica: formulario.tematica.trim() || null, estado: formulario.estado });
      } else {
        guardado = await crearEvento(datos);
      }
      if (archivo) {
        try {
          setProgreso(0);
          guardado = await cargarFlyerEvento(guardado.id, archivo, setProgreso);
        } catch (err) {
          if (!eventoEnEdicion) setEventoEnEdicion(guardado);
          const aviso = `El evento quedó guardado, pero el flyer no se pudo cargar. ${mensajeDeError(err, "Revisa el archivo e inténtalo de nuevo.")}`;
          await cargarEventos();
          setError(aviso);
          return;
        }
      }
      setMensaje(eventoEnEdicion ? "Cambios guardados en la agenda." : "Fecha agregada a la agenda.");
      cancelarEdicion();
      await cargarEventos();
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo guardar el evento."));
    } finally {
      setGuardando(false);
      setProgreso(null);
    }
  }

  async function quitarFlyerActual() {
    if (!eventoEnEdicion?.flyer_url) return;
    setGuardando(true);
    setError(null);
    try {
      const actualizado = await eliminarFlyerEvento(eventoEnEdicion.id);
      setEventoEnEdicion(actualizado);
      setEventos((actuales) => actuales.map((evento) => evento.id === actualizado.id ? actualizado : evento));
      setMensaje("Flyer eliminado de esta fecha.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo eliminar el flyer."));
    } finally {
      setGuardando(false);
    }
  }

  async function elegirArchivo(event) {
    const entrada = event.target;
    const seleccionado = entrada.files?.[0] ?? null;
    setError(null);
    if (!seleccionado) { setArchivo(null); return; }
    const esVideo = seleccionado.type.startsWith("video/");
    if (esVideo && seleccionado.size > MAX_VIDEO) {
      setError("El video no puede superar 20 MB. Comprímelo o recórtalo e inténtalo de nuevo.");
      setArchivo(null); entrada.value = ""; return;
    }
    if (seleccionado.type === "image/gif" && seleccionado.size > 4 * 1024 * 1024) {
      setError("El GIF no puede superar 4 MB. Usa un MP4 para animaciones más pesadas.");
      setArchivo(null); entrada.value = ""; return;
    }
    if (!esVideo && seleccionado.size > MAX_IMAGEN_ORIGINAL) {
      setError("La imagen es demasiado grande (máximo 40 MB).");
      setArchivo(null); entrada.value = ""; return;
    }
    try {
      setArchivo(await prepararFlyer(seleccionado));
    } catch (err) {
      setError(err.message || "No se pudo preparar la imagen.");
      setArchivo(null); entrada.value = "";
    }
  }

  function descartarSeleccion() {
    setArchivo(null);
    const entrada = document.getElementById("agenda-flyer");
    if (entrada) entrada.value = "";
  }

  async function quitarFlyerDe(evento) {
    if (!window.confirm(`¿Quitar el flyer de «${evento.nombre}»? La fecha se queda en la agenda sin imagen.`)) return;
    setError(null);
    try {
      const actualizado = await eliminarFlyerEvento(evento.id);
      setEventos((actuales) => actuales.map((e) => e.id === actualizado.id ? actualizado : e));
      if (eventoEnEdicion?.id === actualizado.id) setEventoEnEdicion(actualizado);
      setMensaje("Flyer eliminado de esta fecha.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo eliminar el flyer."));
    }
  }

  async function eliminarFecha(evento) {
    if (!window.confirm(`¿Eliminar la fecha «${evento.nombre}»? También se borra su flyer. Esta acción no se puede deshacer.`)) return;
    setError(null);
    try {
      await eliminarEvento(evento.id);
      if (eventoEnEdicion?.id === evento.id) cancelarEdicion();
      setMensaje("Fecha eliminada de la agenda.");
      await cargarEventos();
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo eliminar la fecha."));
    }
  }

  const hoy = fechaLocalHoy();
  const proximas = eventos.filter((e) => e.fecha >= hoy && e.estado !== "cerrado").sort((a, b) => a.fecha.localeCompare(b.fecha));
  const anteriores = eventos.filter((e) => !(e.fecha >= hoy && e.estado !== "cerrado")).sort((a, b) => b.fecha.localeCompare(a.fecha));
  const flyerActual = eventoEnEdicion?.flyer_url ? urlFlyerEvento(eventoEnEdicion.flyer_url) : "";

  function tarjeta(evento) {
    return (
      <article className="agenda-event-card" key={evento.id}>
        <div className="agenda-event-poster">
          {evento.flyer_url ? (esVideoEvento(evento.flyer_url) ? <video src={urlFlyerEvento(evento.flyer_url)} muted loop playsInline autoPlay preload="metadata" aria-label={`Video de ${evento.nombre}`} /> : <img src={urlFlyerEvento(evento.flyer_url)} alt={`Flyer de ${evento.nombre}`} />) : <div className="agenda-poster-empty"><span>MEDALLO CLUB</span><strong>{evento.tematica || "Próxima fecha"}</strong></div>}
          <span className={`agenda-event-status status-${evento.estado.replace(" ", "-")}`}>{evento.estado}</span>
        </div>
        <div className="agenda-event-copy"><p>{fechaLegible(evento.fecha)}</p><h3>{evento.nombre}</h3><span>{evento.tematica || "Sin temática agregada"}</span><small>Aforo: {evento.aforo_maximo} personas</small></div>
        <div className="agenda-event-actions">
          <button className="btn btn-outline btn-sm" type="button" onClick={() => editar(evento)}>Editar fecha</button>
          {evento.flyer_url && <button className="btn btn-outline btn-sm" type="button" onClick={() => quitarFlyerDe(evento)}>Quitar flyer</button>}
          <button className="btn btn-outline btn-sm agenda-eliminar" type="button" onClick={() => eliminarFecha(evento)}>Eliminar fecha</button>
        </div>
      </article>
    );
  }

  return (
    <div className="agenda-admin-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">CONTENIDO PÚBLICO</p>
          <h1>Agenda y flyers</h1>
          <p className="page-subtitle">Publica cada fecha, su temática y el arte del evento.</p>
        </div>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}
      {mensaje && <div className="agenda-aviso" role="status">{mensaje}</div>}

      <section className="card agenda-editor">
        <div className="section-heading"><div><p className="section-kicker">{eventoEnEdicion ? "ACTUALIZAR FECHA" : "NUEVA FECHA"}</p><h2>{eventoEnEdicion ? "Editar evento" : "Crear evento"}</h2></div>{eventoEnEdicion && <button className="btn btn-outline btn-sm" type="button" onClick={cancelarEdicion}>Cancelar edición</button>}</div>
        <form className="agenda-form" onSubmit={guardar}>
          <div className="form-field"><label htmlFor="agenda-nombre">Nombre del evento</label><input id="agenda-nombre" name="nombre" maxLength="100" required value={formulario.nombre} onChange={cambiarCampo} placeholder="Ej. Jueves de trap y perreo" /></div>
          <div className="agenda-form-row">
            <div className="form-field"><label htmlFor="agenda-fecha">Fecha</label><input id="agenda-fecha" name="fecha" type="date" required value={formulario.fecha} onChange={cambiarCampo} /></div>
            <div className="form-field"><label htmlFor="agenda-aforo">Aforo máximo</label><input id="agenda-aforo" name="aforo_maximo" type="number" min="1" required value={formulario.aforo_maximo} onChange={cambiarCampo} /></div>
            {eventoEnEdicion && <div className="form-field"><label htmlFor="agenda-estado">Estado</label><select id="agenda-estado" name="estado" value={formulario.estado} onChange={cambiarCampo}><option value="planeado">Planeado</option><option value="en curso">En curso</option><option value="cerrado">Cerrado</option></select></div>}
          </div>
          <div className="form-field"><label htmlFor="agenda-tematica">Temática del día</label><input id="agenda-tematica" name="tematica" maxLength="240" value={formulario.tematica} onChange={cambiarCampo} placeholder="Ej. Noche de reggaetón clásico" /></div>
          <div className="form-field agenda-upload-field">
            <label htmlFor="agenda-flyer">Flyer o video del evento <span>(imagen JPG, PNG, WEBP o GIF; video MP4 o WEBM hasta 20 MB. Las imágenes grandes se reducen solas)</span></label>
            <input id="agenda-flyer" type="file" accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/webm" onChange={elegirArchivo} />
            {(vistaPrevia || flyerActual) && (
              <div className="agenda-flyer-preview">
                {esVideoEvento(archivo?.name || flyerActual) ? <video src={vistaPrevia || flyerActual} controls muted playsInline preload="metadata" /> : <img src={vistaPrevia || flyerActual} alt="Vista previa del flyer" />}
                <span>{archivo ? `${archivo.name} (${(archivo.size / 1024 / 1024).toFixed(1)} MB)` : "Contenido actual"}</span>
                {archivo && <button className="btn btn-outline btn-sm" type="button" disabled={guardando} onClick={descartarSeleccion}>Descartar selección</button>}
                {flyerActual && !archivo && <button className="btn btn-outline btn-sm agenda-eliminar" type="button" disabled={guardando} onClick={quitarFlyerActual}>Quitar archivo</button>}
              </div>
            )}
          </div>
          <button className="btn btn-primary" type="submit" disabled={guardando}>{guardando ? (progreso !== null ? `Subiendo flyer… ${progreso}%` : "Guardando…") : eventoEnEdicion ? "Guardar cambios" : "Publicar evento"}</button>
        </form>
      </section>

      <section className="agenda-list-section">
        <div className="section-heading"><div><p className="section-kicker">PROGRAMACIÓN</p><h2>Próximas fechas</h2></div><span className="agenda-total">{proximas.length}</span></div>
        {cargando ? <p className="agenda-empty">Cargando agenda…</p> : eventos.length === 0 ? <p className="agenda-empty">Todavía no hay eventos. Crea una fecha para empezar.</p> : proximas.length === 0 ? <p className="agenda-empty">No hay fechas próximas. Crea una nueva arriba.</p> : (
          <div className="agenda-event-grid">{proximas.map(tarjeta)}</div>
        )}
      </section>

      {anteriores.length > 0 && (
        <section className="agenda-list-section agenda-pasadas">
          <div className="section-heading"><div><p className="section-kicker">HISTORIAL</p><h2>Fechas pasadas o cerradas</h2></div><span className="agenda-total">{anteriores.length}</span></div>
          <div className="agenda-event-grid">{anteriores.map(tarjeta)}</div>
        </section>
      )}
    </div>
  );
}
