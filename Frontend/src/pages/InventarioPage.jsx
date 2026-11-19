import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { AlertBanner } from "../components/AlertBanner";
import { mensajeDeError } from "../services/apiClient";
import { listarEventos } from "../services/eventosService";
import {
  actualizarItemInventario,
  crearItemInventario,
  eliminarItemInventario,
  exportarInventarioCsv,
  listarHistorialItem,
  listarInventario,
  listarMovimientosInventario,
  obtenerConsumoEvento,
  obtenerResumenInventario,
  registrarMovimientoInventario,
} from "../services/inventarioService";
import "./InventarioPage.css";

const TIPOS_MOVIMIENTO = {
  entrada: { etiqueta: "Entrada", glifo: "+", ayuda: "Suma unidades al inventario." },
  salida: { etiqueta: "Salida", glifo: "−", ayuda: "Retira unidades (venta, merma, traslado)." },
  consumo: { etiqueta: "Consumo", glifo: "◔", ayuda: "Unidades usadas en un evento." },
  ajuste: { etiqueta: "Ajuste", glifo: "⇄", ayuda: "Fija el conteo físico real." },
};

const ESTADOS = {
  ok: { etiqueta: "Disponible", clase: "ok" },
  bajo: { etiqueta: "Stock bajo", clase: "bajo" },
  agotado: { etiqueta: "Agotado", clase: "agotado" },
};

const formatoNumero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });
const formatoCOP = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const formatoCOPDetalle = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 });

const cantidadTexto = (valor) => formatoNumero.format(Number(valor ?? 0));
const redondear = (valor) => Math.round(valor * 100) / 100;

// Ganancia por unidad a partir del costo y del valor de venta (solo si ambos están escritos).
function margenTexto(costo, venta) {
  if (costo === "" || venta === "" || costo == null || venta == null) return "";
  const c = Number(costo);
  const v = Number(venta);
  if (!Number.isFinite(c) || !Number.isFinite(v) || v <= 0) return "";
  const ganancia = v - c;
  const porcentaje = Math.round((ganancia / v) * 100);
  return `Ganancia por unidad: ${formatoCOPDetalle.format(ganancia)} (${porcentaje} % sobre la venta).`;
}

function normalizar(texto) {
  return String(texto ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function fechaUtc(valor) {
  if (!valor) return null;
  const texto = String(valor);
  const fecha = new Date(/(Z|[+-]\d{2}:?\d{2})$/.test(texto) ? texto : `${texto}Z`);
  return Number.isNaN(fecha.getTime()) ? null : fecha;
}

function fechaHora(valor) {
  const fecha = fechaUtc(valor);
  return fecha ? fecha.toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) : "";
}

function fechaEvento(valor) {
  if (!valor) return "";
  const texto = String(valor);
  const fecha = new Date(/^\d{4}-\d{2}-\d{2}$/.test(texto) ? `${texto}T00:00:00` : texto);
  return Number.isNaN(fecha.getTime()) ? texto : fecha.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

function nivelStock(item) {
  const cantidad = Number(item.cantidad);
  const objetivo = Number(item.stock_minimo) * 2;
  if (objetivo <= 0) return cantidad > 0 ? 100 : 0;
  return Math.max(0, Math.min(100, (cantidad / objetivo) * 100));
}

function deltaMovimiento(mov) {
  if (mov.tipo === "entrada") return Number(mov.cantidad);
  if (mov.tipo === "ajuste") return redondear(Number(mov.cantidad_nueva) - Number(mov.cantidad_anterior));
  return -Number(mov.cantidad);
}

function formatoDelta(delta) {
  if (delta === 0) return "0";
  return `${delta > 0 ? "+" : "−"}${formatoNumero.format(Math.abs(delta))}`;
}

function Modal({ titulo, eyebrow, onClose, children, ancho = "md" }) {
  const idTitulo = useId();
  const dialogoRef = useRef(null);
  const alCerrar = useRef(onClose);

  useEffect(() => {
    alCerrar.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const previo = document.activeElement;
    const dialogo = dialogoRef.current;
    const campo = dialogo?.querySelector(".inv-modal-body input:not([disabled]), .inv-modal-body select:not([disabled]), .inv-modal-body textarea:not([disabled])");
    (campo ?? dialogo)?.focus();
    const overflowPrevio = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    function teclado(event) {
      if (event.key === "Escape") {
        event.stopPropagation();
        alCerrar.current();
        return;
      }
      if (event.key !== "Tab" || !dialogo) return;
      const enfocables = [...dialogo.querySelectorAll("a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])")];
      if (enfocables.length === 0) return;
      const primero = enfocables[0];
      const ultimo = enfocables[enfocables.length - 1];
      if (event.shiftKey && (document.activeElement === primero || document.activeElement === dialogo)) {
        event.preventDefault();
        ultimo.focus();
      } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primero.focus();
      }
    }
    document.addEventListener("keydown", teclado);
    return () => {
      document.removeEventListener("keydown", teclado);
      document.body.style.overflow = overflowPrevio;
      if (previo instanceof HTMLElement && document.contains(previo)) previo.focus();
    };
  }, []);

  return (
    <div className="inv-overlay" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialogoRef} className={`inv-modal inv-modal-${ancho}`} role="dialog" aria-modal="true" aria-labelledby={idTitulo} tabIndex={-1}>
        <header className="inv-modal-header">
          <div>
            {eyebrow && <p className="inv-eyebrow">{eyebrow}</p>}
            <h2 id={idTitulo}>{titulo}</h2>
          </div>
          <button className="inv-modal-close" type="button" onClick={onClose} aria-label="Cerrar">×</button>
        </header>
        <div className="inv-modal-body">{children}</div>
      </section>
    </div>
  );
}

function ModalMovimiento({ item, tipoInicial, cantidadInicial, eventos, onClose, onGuardado }) {
  const [tipo, setTipo] = useState(tipoInicial);
  const [cantidad, setCantidad] = useState(cantidadInicial);
  const [motivo, setMotivo] = useState("");
  const [eventoId, setEventoId] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const idBase = useId();

  const actual = Number(item.cantidad);
  const valor = cantidad === "" ? NaN : Number(cantidad);
  const valido = Number.isFinite(valor) && (tipo === "ajuste" ? valor >= 0 : valor > 0);
  let resultado = null;
  if (valido) {
    if (tipo === "entrada") resultado = actual + valor;
    else if (tipo === "ajuste") resultado = valor;
    else resultado = actual - valor;
    resultado = redondear(resultado);
  }
  const excede = resultado !== null && resultado < 0;
  const usaEvento = tipo === "consumo" || tipo === "salida";

  async function guardar(event) {
    event.preventDefault();
    if (!valido || excede) return;
    setGuardando(true);
    setError(null);
    try {
      const respuesta = await registrarMovimientoInventario(item.id, {
        tipo,
        cantidad: valor,
        motivo: motivo.trim() || null,
        evento_id: eventoId ? Number(eventoId) : null,
      });
      onGuardado(respuesta, tipo);
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo registrar el movimiento."));
      setGuardando(false);
    }
  }

  return (
    <Modal titulo={item.nombre} eyebrow="REGISTRAR MOVIMIENTO" onClose={onClose}>
      <form onSubmit={guardar}>
        <p className="inv-current">Existencias actuales: <strong>{cantidadTexto(item.cantidad)} {item.unidad}</strong></p>
        <div className="form-field">
          <label htmlFor={`${idBase}-tipo`}>Tipo de movimiento</label>
          <select id={`${idBase}-tipo`} value={tipo} onChange={(event) => setTipo(event.target.value)}>
            {Object.entries(TIPOS_MOVIMIENTO).map(([clave, datos]) => <option key={clave} value={clave}>{datos.etiqueta}</option>)}
          </select>
          <small className="inv-hint">{TIPOS_MOVIMIENTO[tipo].ayuda}</small>
        </div>
        <div className="form-field">
          <label htmlFor={`${idBase}-cantidad`}>{tipo === "ajuste" ? "Conteo físico final" : "Cantidad"} ({item.unidad})</label>
          <input id={`${idBase}-cantidad`} type="number" inputMode="decimal" min={tipo === "ajuste" ? "0" : "0.01"} step="0.01" required value={cantidad} onChange={(event) => setCantidad(event.target.value)} />
        </div>
        {resultado !== null && (
          <p className={`inv-preview${excede ? " is-error" : ""}`} aria-live="polite">
            {excede
              ? `No hay suficientes existencias: solo hay ${cantidadTexto(actual)} ${item.unidad}.`
              : <>Quedará en <strong>{cantidadTexto(resultado)} {item.unidad}</strong></>}
          </p>
        )}
        <div className="form-field">
          <label htmlFor={`${idBase}-motivo`}>Motivo <span className="inv-optional">(opcional)</span></label>
          <input id={`${idBase}-motivo`} maxLength="200" value={motivo} onChange={(event) => setMotivo(event.target.value)} placeholder="Ej. Compra a proveedor, conteo de cierre…" />
        </div>
        <div className="form-field">
          <label htmlFor={`${idBase}-evento`}>Evento <span className="inv-optional">(opcional{usaEvento ? "" : ", útil en consumo y salida"})</span></label>
          <select id={`${idBase}-evento`} value={eventoId} onChange={(event) => setEventoId(event.target.value)}>
            <option value="">Sin evento</option>
            {eventos.map((evento) => <option key={evento.id} value={evento.id}>{evento.nombre}{evento.fecha ? ` · ${fechaEvento(evento.fecha)}` : ""}</option>)}
          </select>
        </div>
        {error && <p className="inv-form-error" role="alert">{error}</p>}
        <div className="inv-modal-actions">
          <button className="btn btn-outline" type="button" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" type="submit" disabled={guardando || !valido || excede}>{guardando ? "Guardando…" : "Registrar movimiento"}</button>
        </div>
      </form>
    </Modal>
  );
}

function ModalProducto({ item, categorias, onClose, onGuardado }) {
  const editando = Boolean(item);
  const [formulario, setFormulario] = useState(() => ({
    nombre: item?.nombre ?? "",
    categoria: item?.categoria ?? "",
    cantidad: item ? String(Number(item.cantidad)) : "0",
    unidad: item?.unidad ?? "unidades",
    stock_minimo: item ? String(Number(item.stock_minimo)) : "0",
    costo_unitario: item?.costo_unitario != null ? String(Number(item.costo_unitario)) : "",
    precio_venta: item?.precio_venta != null ? String(Number(item.precio_venta)) : "",
    proveedor: item?.proveedor ?? "",
  }));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState(null);
  const idBase = useId();

  function cambiar(event) {
    const { name, value } = event.target;
    setFormulario((actual) => ({ ...actual, [name]: value }));
  }

  async function guardar(event) {
    event.preventDefault();
    setGuardando(true);
    setError(null);
    const payload = {
      nombre: formulario.nombre.trim(),
      categoria: formulario.categoria.trim() || null,
      cantidad: Number(formulario.cantidad),
      unidad: formulario.unidad.trim(),
      stock_minimo: Number(formulario.stock_minimo),
      costo_unitario: formulario.costo_unitario === "" ? null : Number(formulario.costo_unitario),
      precio_venta: formulario.precio_venta === "" ? null : Number(formulario.precio_venta),
      proveedor: formulario.proveedor.trim() || null,
    };
    try {
      if (editando) await actualizarItemInventario(item.id, payload);
      else await crearItemInventario(payload);
      onGuardado(editando ? "Producto actualizado." : "Producto agregado al inventario.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo guardar el producto."));
      setGuardando(false);
    }
  }

  const cambioCantidad = editando && Number(formulario.cantidad) !== Number(item.cantidad);

  return (
    <Modal titulo={editando ? "Editar producto" : "Nuevo producto"} eyebrow={editando ? "INVENTARIO" : "AGREGAR AL INVENTARIO"} onClose={onClose} ancho="lg">
      <form onSubmit={guardar}>
        <div className="inv-form-grid">
          <div className="form-field inv-span-2">
            <label htmlFor={`${idBase}-nombre`}>Producto</label>
            <input id={`${idBase}-nombre`} name="nombre" minLength="2" maxLength="100" required value={formulario.nombre} onChange={cambiar} placeholder="Ej. Aguardiente tradicional 750 ml" />
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-categoria`}>Categoría <span className="inv-optional">(opcional)</span></label>
            <input id={`${idBase}-categoria`} name="categoria" maxLength="60" list={`${idBase}-categorias`} value={formulario.categoria} onChange={cambiar} placeholder="Licores, mezcladores…" />
            <datalist id={`${idBase}-categorias`}>{categorias.map((categoria) => <option key={categoria} value={categoria} />)}</datalist>
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-cantidad`}>Cantidad disponible</label>
            <input id={`${idBase}-cantidad`} name="cantidad" type="number" inputMode="decimal" min="0" step="0.01" required value={formulario.cantidad} onChange={cambiar} />
            {editando && <small className="inv-hint">Los cambios de cantidad quedan registrados como ajuste.</small>}
            {cambioCantidad && <small className="inv-hint inv-hint-warn">Se registrará un ajuste de {cantidadTexto(item.cantidad)} a {cantidadTexto(formulario.cantidad || 0)}.</small>}
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-unidad`}>Unidad</label>
            <input id={`${idBase}-unidad`} name="unidad" minLength="1" maxLength="20" required value={formulario.unidad} onChange={cambiar} placeholder="botellas, cajas, kg…" />
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-minimo`}>Avisarme al llegar a</label>
            <input id={`${idBase}-minimo`} name="stock_minimo" type="number" inputMode="decimal" min="0" step="0.01" required value={formulario.stock_minimo} onChange={cambiar} />
            <small className="inv-hint">Se marca como bajo cuando la cantidad llega a este nivel.</small>
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-costo`}>Valor unitario / costo (COP) <span className="inv-optional">(opcional)</span></label>
            <input id={`${idBase}-costo`} name="costo_unitario" type="number" inputMode="decimal" min="0" step="0.01" value={formulario.costo_unitario} onChange={cambiar} placeholder="0" />
            <small className="inv-hint">Lo que le cuesta al club cada unidad.</small>
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-venta`}>Valor de venta en la discoteca (COP) <span className="inv-optional">(opcional)</span></label>
            <input id={`${idBase}-venta`} name="precio_venta" type="number" inputMode="decimal" min="0" step="0.01" value={formulario.precio_venta} onChange={cambiar} placeholder="0" />
            {margenTexto(formulario.costo_unitario, formulario.precio_venta) && <small className="inv-hint">{margenTexto(formulario.costo_unitario, formulario.precio_venta)}</small>}
          </div>
          <div className="form-field">
            <label htmlFor={`${idBase}-proveedor`}>Proveedor <span className="inv-optional">(opcional)</span></label>
            <input id={`${idBase}-proveedor`} name="proveedor" maxLength="100" value={formulario.proveedor} onChange={cambiar} />
          </div>
        </div>
        {error && <p className="inv-form-error" role="alert">{error}</p>}
        <div className="inv-modal-actions">
          <button className="btn btn-outline" type="button" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" type="submit" disabled={guardando}>{guardando ? "Guardando…" : editando ? "Guardar cambios" : "Agregar producto"}</button>
        </div>
      </form>
    </Modal>
  );
}

function FilaMovimiento({ mov, nombresEventos, mostrarProducto }) {
  const datos = TIPOS_MOVIMIENTO[mov.tipo] ?? { etiqueta: mov.tipo, glifo: "•" };
  const delta = deltaMovimiento(mov);
  const evento = mov.evento_id ? (nombresEventos.get(mov.evento_id) ?? `Evento #${mov.evento_id}`) : null;
  return (
    <li className={`inv-mov tipo-${mov.tipo}`}>
      <span className="inv-mov-icon" aria-hidden="true">{datos.glifo}</span>
      <div className="inv-mov-body">
        <div className="inv-mov-top">
          <strong>{mostrarProducto && mov.item_nombre ? `${mov.item_nombre} · ` : ""}{datos.etiqueta}</strong>
          <span className={`inv-mov-delta${delta > 0 ? " up" : delta < 0 ? " down" : ""}`}>{formatoDelta(delta)}</span>
        </div>
        <p className="inv-mov-change">{cantidadTexto(mov.cantidad_anterior)} → {cantidadTexto(mov.cantidad_nueva)}</p>
        {(mov.motivo || evento) && <p className="inv-mov-note">{mov.motivo}{mov.motivo && evento ? " · " : ""}{evento && <span className="inv-mov-event">{evento}</span>}</p>}
        <time className="inv-mov-date" dateTime={mov.creado_en}>{fechaHora(mov.creado_en)}</time>
      </div>
    </li>
  );
}

function ModalHistorial({ item, nombresEventos, onClose }) {
  const [movimientos, setMovimientos] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let vigente = true;
    listarHistorialItem(item.id, 100)
      .then((datos) => { if (vigente) setMovimientos(datos); })
      .catch((err) => { if (vigente) setError(mensajeDeError(err, "No fue posible cargar el historial.")); });
    return () => { vigente = false; };
  }, [item.id]);

  return (
    <Modal titulo={item.nombre} eyebrow="HISTORIAL DE MOVIMIENTOS" onClose={onClose}>
      {error ? <p className="inv-form-error" role="alert">{error}</p>
        : movimientos === null ? <p className="inv-empty">Cargando historial…</p>
        : movimientos.length === 0 ? <p className="inv-empty">Este producto aún no tiene movimientos.</p>
        : <ul className="inv-mov-list" aria-label={`Movimientos de ${item.nombre}`}>
          {movimientos.map((mov) => <FilaMovimiento key={mov.id} mov={mov} nombresEventos={nombresEventos} />)}
        </ul>}
      <div className="inv-modal-actions">
        <button className="btn btn-outline" type="button" onClick={onClose}>Cerrar</button>
      </div>
    </Modal>
  );
}

function BarraNivel({ item }) {
  return (
    <div className={`inv-level estado-${item.estado_stock}`}>
      <div className="inv-level-text">
        <strong>{cantidadTexto(item.cantidad)}</strong> {item.unidad}
        <span>mín. {cantidadTexto(item.stock_minimo)}</span>
      </div>
      <div className="inv-level-track" aria-hidden="true"><div className="inv-level-fill" style={{ width: `${nivelStock(item)}%` }} /></div>
    </div>
  );
}

export function InventarioPage() {
  const [items, setItems] = useState([]);
  const [resumen, setResumen] = useState(null);
  const [eventos, setEventos] = useState([]);
  const [version, setVersion] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState(null);
  const [exito, setExito] = useState(null);
  const [exportando, setExportando] = useState(false);
  const [pestana, setPestana] = useState("existencias");
  const [busqueda, setBusqueda] = useState("");
  const [filtroCategoria, setFiltroCategoria] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("");
  const [modal, setModal] = useState(null);
  const [movimientos, setMovimientos] = useState(null);
  const [errorMovimientos, setErrorMovimientos] = useState(null);
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroEvento, setFiltroEvento] = useState("");
  const [eventoConsumo, setEventoConsumo] = useState("");
  const [consumo, setConsumo] = useState(null);
  const [cargandoConsumo, setCargandoConsumo] = useState(false);
  const [errorConsumo, setErrorConsumo] = useState(null);
  const solicitudConsumo = useRef(0);
  const temporizadorExito = useRef(null);

  const refrescar = useCallback(() => setVersion((actual) => actual + 1), []);

  useEffect(() => {
    let vigente = true;
    Promise.all([listarInventario(), obtenerResumenInventario()])
      .then(([lista, datosResumen]) => {
        if (!vigente) return;
        setItems(lista);
        setResumen(datosResumen);
        setError(null);
      })
      .catch((err) => { if (vigente) setError(mensajeDeError(err, "No fue posible cargar el inventario.")); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [version]);

  useEffect(() => {
    let vigente = true;
    listarEventos({ page: 1, limit: 100 })
      .then((datos) => { if (vigente) setEventos(Array.isArray(datos?.items) ? datos.items : []); })
      .catch(() => { if (vigente) setEventos([]); });
    return () => { vigente = false; };
  }, []);

  useEffect(() => {
    if (pestana !== "movimientos") return undefined;
    let vigente = true;
    listarMovimientosInventario({ tipo: filtroTipo, eventoId: filtroEvento, limite: 100 })
      .then((datos) => {
        if (!vigente) return;
        setMovimientos(datos);
        setErrorMovimientos(null);
      })
      .catch((err) => { if (vigente) setErrorMovimientos(mensajeDeError(err, "No fue posible cargar los movimientos.")); });
    return () => { vigente = false; };
  }, [pestana, filtroTipo, filtroEvento, version]);

  useEffect(() => () => window.clearTimeout(temporizadorExito.current), []);

  const notificarExito = useCallback((texto) => {
    window.clearTimeout(temporizadorExito.current);
    setExito(texto);
    temporizadorExito.current = window.setTimeout(() => setExito(null), 5000);
  }, []);

  const nombresEventos = useMemo(() => new Map(eventos.map((evento) => [evento.id, evento.nombre])), [eventos]);

  const categorias = useMemo(() => {
    const conjunto = new Set(items.map((item) => item.categoria).filter(Boolean));
    return [...conjunto].sort((a, b) => a.localeCompare(b, "es"));
  }, [items]);

  const itemsFiltrados = useMemo(() => {
    const termino = normalizar(busqueda.trim());
    return items.filter((item) => {
      if (termino && !normalizar(item.nombre).includes(termino)) return false;
      if (filtroCategoria && item.categoria !== filtroCategoria) return false;
      if (filtroEstado && item.estado_stock !== filtroEstado) return false;
      return true;
    });
  }, [items, busqueda, filtroCategoria, filtroEstado]);

  const porReponer = useMemo(() => {
    const orden = { agotado: 0, bajo: 1 };
    return items
      .filter((item) => item.estado_stock !== "ok")
      .sort((a, b) => orden[a.estado_stock] - orden[b.estado_stock] || a.nombre.localeCompare(b.nombre, "es"));
  }, [items]);

  const hayFiltros = Boolean(busqueda.trim() || filtroCategoria || filtroEstado);
  const maxConsumo = Math.max(0, ...(resumen?.mayor_consumo_7d ?? []).map((fila) => Number(fila.cantidad)));
  const maxValorCategoria = Math.max(0, ...(resumen?.categorias ?? []).map((fila) => Number(fila.valor)));

  function abrirMovimiento(item, tipo, cantidad = "") {
    setModal({ clase: "movimiento", item, tipo, cantidad });
  }

  function alRegistrarMovimiento(respuesta, tipo) {
    const { item } = respuesta;
    setModal(null);
    notificarExito(`${TIPOS_MOVIMIENTO[tipo].etiqueta} registrada: ${item.nombre} queda en ${cantidadTexto(item.cantidad)} ${item.unidad}.`);
    refrescar();
  }

  function alGuardarProducto(texto) {
    setModal(null);
    notificarExito(texto);
    refrescar();
  }

  async function eliminar(item) {
    if (!window.confirm(`¿Eliminar "${item.nombre}" del inventario? Se borrará también su historial de movimientos. Esta acción no se puede deshacer.`)) return;
    setError(null);
    try {
      await eliminarItemInventario(item.id);
      notificarExito(`Producto "${item.nombre}" eliminado.`);
      refrescar();
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo eliminar el producto."));
    }
  }

  async function exportar() {
    setExportando(true);
    setError(null);
    try {
      await exportarInventarioCsv();
      notificarExito("Exportación lista: inventario-medallo-club.csv.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo exportar el inventario."));
    } finally {
      setExportando(false);
    }
  }

  async function elegirEventoConsumo(valor) {
    setEventoConsumo(valor);
    setErrorConsumo(null);
    const numero = solicitudConsumo.current + 1;
    solicitudConsumo.current = numero;
    if (!valor) {
      setConsumo(null);
      setCargandoConsumo(false);
      return;
    }
    setCargandoConsumo(true);
    try {
      const datos = await obtenerConsumoEvento(valor);
      if (solicitudConsumo.current === numero) setConsumo(datos);
    } catch (err) {
      if (solicitudConsumo.current === numero) {
        setConsumo(null);
        setErrorConsumo(mensajeDeError(err, "No fue posible cargar el consumo del evento."));
      }
    } finally {
      if (solicitudConsumo.current === numero) setCargandoConsumo(false);
    }
  }

  function limpiarFiltros() {
    setBusqueda("");
    setFiltroCategoria("");
    setFiltroEstado("");
  }

  function teclasPestanas(event) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const siguiente = pestana === "existencias" ? "movimientos" : "existencias";
    setPestana(siguiente);
    document.getElementById(`inv-tab-${siguiente}`)?.focus();
  }

  const kpis = resumen ? [
    { clave: "productos", etiqueta: "Productos", valor: resumen.productos },
    { clave: "minimo", etiqueta: "En nivel mínimo", valor: resumen.en_minimo, clase: resumen.en_minimo > 0 ? "is-warn" : "" },
    { clave: "agotados", etiqueta: "Agotados", valor: resumen.agotados, clase: resumen.agotados > 0 ? "is-danger" : "" },
    { clave: "valor", etiqueta: "Valor del inventario", valor: formatoCOP.format(Number(resumen.valor_total)) },
    { clave: "hoy", etiqueta: "Movimientos hoy", valor: resumen.movimientos_hoy },
  ] : [];

  return (
    <div className="inventario-page">
      <div className="page-header">
        <div className="page-heading">
          <p className="page-eyebrow">CONTROL DE EXISTENCIAS</p>
          <h1>Inventario</h1>
          <p className="page-subtitle">Controla existencias, registra entradas y consumos, y recibe avisos antes de quedarte sin producto.</p>
        </div>
        <div className="inv-header-actions">
          <button className="btn btn-outline" type="button" onClick={exportar} disabled={exportando || cargando}>{exportando ? "Exportando…" : "Exportar CSV"}</button>
          <button className="btn btn-primary" type="button" onClick={() => setModal({ clase: "producto", item: null })}>Nuevo producto</button>
        </div>
      </div>

      {error && <AlertBanner nivel="alto">{error}</AlertBanner>}

      {cargando ? <p className="inv-empty" role="status">Cargando inventario…</p> : (
        <>
          <section className="kpi-grid inv-kpis" aria-label="Resumen del inventario">
            {kpis.map((kpi) => (
              <div className={`kpi-card ${kpi.clase ?? ""}`} key={kpi.clave}>
                <div className="kpi-label">{kpi.etiqueta}</div>
                <div className="kpi-value">{typeof kpi.valor === "number" ? formatoNumero.format(kpi.valor) : kpi.valor}</div>
              </div>
            ))}
          </section>

          {resumen && (
            <div className="inv-panels">
              <section className="card inv-panel" aria-labelledby="inv-consumo-titulo">
                <h2 id="inv-consumo-titulo">Mayor consumo (7 días)</h2>
                {resumen.mayor_consumo_7d.length === 0 ? <p className="inv-empty">Sin consumos ni salidas en los últimos 7 días.</p> : (
                  <ul className="inv-bars">
                    {resumen.mayor_consumo_7d.map((fila) => (
                      <li key={fila.item_id}>
                        <div className="inv-bars-label"><span>{fila.nombre}</span><strong>{cantidadTexto(fila.cantidad)} {fila.unidad}</strong></div>
                        <div className="inv-bars-track" aria-hidden="true"><div className="inv-bars-fill consumo" style={{ width: `${maxConsumo ? (Number(fila.cantidad) / maxConsumo) * 100 : 0}%` }} /></div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
              <section className="card inv-panel" aria-labelledby="inv-categorias-titulo">
                <h2 id="inv-categorias-titulo">Valor por categoría</h2>
                {resumen.categorias.length === 0 ? <p className="inv-empty">Aún no hay productos con categoría.</p> : (
                  <ul className="inv-bars">
                    {resumen.categorias.map((fila) => (
                      <li key={fila.categoria}>
                        <div className="inv-bars-label"><span>{fila.categoria} <small>· {fila.productos} prod.</small></span><strong>{formatoCOP.format(Number(fila.valor))}</strong></div>
                        <div className="inv-bars-track" aria-hidden="true"><div className="inv-bars-fill valor" style={{ width: `${maxValorCategoria ? (Number(fila.valor) / maxValorCategoria) * 100 : 0}%` }} /></div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}

          {porReponer.length > 0 && (
            <section className="card inv-alerta" aria-labelledby="inv-alerta-titulo">
              <p className="inv-eyebrow">AVISO DE EXISTENCIAS</p>
              <h2 id="inv-alerta-titulo">{porReponer.length} producto{porReponer.length === 1 ? "" : "s"} por reponer</h2>
              <ul className="inv-alerta-list">
                {porReponer.map((item) => (
                  <li key={item.id}>
                    <div className="inv-alerta-info">
                      <span className={`inv-badge ${ESTADOS[item.estado_stock].clase}`}>{ESTADOS[item.estado_stock].etiqueta}</span>
                      <span><strong>{item.nombre}</strong> · {cantidadTexto(item.cantidad)} {item.unidad}</span>
                      {Number(item.reposicion_sugerida) > 0 && <small>Sugerido: {cantidadTexto(item.reposicion_sugerida)} {item.unidad}</small>}
                    </div>
                    <button className="btn btn-outline btn-sm" type="button" onClick={() => abrirMovimiento(item, "entrada", Number(item.reposicion_sugerida) > 0 ? String(Number(item.reposicion_sugerida)) : "")}>Reponer</button>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="inv-tabs" role="tablist" aria-label="Secciones del inventario" onKeyDown={teclasPestanas}>
            {[["existencias", "Existencias"], ["movimientos", "Movimientos"]].map(([clave, etiqueta]) => (
              <button key={clave} id={`inv-tab-${clave}`} className={`inv-tab${pestana === clave ? " active" : ""}`} type="button" role="tab" aria-selected={pestana === clave} aria-controls={`inv-panel-${clave}`} tabIndex={pestana === clave ? 0 : -1} onClick={() => setPestana(clave)}>{etiqueta}</button>
            ))}
          </div>

          {pestana === "existencias" && (
            <section className="card inv-section" id="inv-panel-existencias" role="tabpanel" aria-labelledby="inv-tab-existencias">
              <div className="inv-filters">
                <div className="form-field">
                  <label htmlFor="inv-buscar">Buscar</label>
                  <input id="inv-buscar" type="search" value={busqueda} onChange={(event) => setBusqueda(event.target.value)} placeholder="Nombre del producto…" />
                </div>
                <div className="form-field">
                  <label htmlFor="inv-categoria">Categoría</label>
                  <select id="inv-categoria" value={filtroCategoria} onChange={(event) => setFiltroCategoria(event.target.value)}>
                    <option value="">Todas</option>
                    {categorias.map((categoria) => <option key={categoria} value={categoria}>{categoria}</option>)}
                  </select>
                </div>
                <div className="form-field">
                  <label htmlFor="inv-estado">Estado</label>
                  <select id="inv-estado" value={filtroEstado} onChange={(event) => setFiltroEstado(event.target.value)}>
                    <option value="">Todos</option>
                    <option value="ok">Disponible</option>
                    <option value="bajo">Stock bajo</option>
                    <option value="agotado">Agotado</option>
                  </select>
                </div>
                {hayFiltros && <button className="btn btn-outline btn-sm inv-clear" type="button" onClick={limpiarFiltros}>Limpiar filtros</button>}
              </div>

              {itemsFiltrados.length === 0 ? (
                <p className="inv-empty">{items.length === 0 ? "Aún no hay productos. Agrega el primero con “Nuevo producto”." : "Ningún producto coincide con los filtros."}</p>
              ) : (
                <ul className="inv-list" aria-label="Productos del inventario">
                  {itemsFiltrados.map((item) => {
                    const valorStock = Number(item.cantidad) * Number(item.costo_unitario ?? 0);
                    const estado = ESTADOS[item.estado_stock];
                    return (
                      <li className={`inv-row estado-${item.estado_stock}`} key={item.id}>
                        <div className="inv-row-main">
                          <strong>{item.nombre}</strong>
                          <span>{item.categoria || "Sin categoría"}</span>
                        </div>
                        <BarraNivel item={item} />
                        <div className="inv-row-status"><span className={`inv-badge ${estado.clase}`}>{estado.etiqueta}</span></div>
                        <dl className="inv-row-money">
                          <div><dt>Costo</dt><dd>{item.costo_unitario != null ? formatoCOPDetalle.format(Number(item.costo_unitario)) : "—"}</dd></div>
                          <div><dt>Venta</dt><dd>{item.precio_venta != null ? formatoCOPDetalle.format(Number(item.precio_venta)) : "—"}</dd></div>
                          <div><dt>En stock</dt><dd>{item.costo_unitario != null ? formatoCOP.format(valorStock) : "—"}</dd></div>
                          <div><dt>Proveedor</dt><dd>{item.proveedor || "—"}</dd></div>
                        </dl>
                        <div className="inv-row-actions">
                          {["entrada", "salida", "consumo"].map((tipo) => (
                            <button key={tipo} className="btn btn-outline btn-sm" type="button" onClick={() => abrirMovimiento(item, tipo)} aria-label={`${TIPOS_MOVIMIENTO[tipo].etiqueta} de ${item.nombre}`}>{TIPOS_MOVIMIENTO[tipo].etiqueta}</button>
                          ))}
                          <button className="btn btn-outline btn-sm" type="button" onClick={() => abrirMovimiento(item, "ajuste", String(Number(item.cantidad)))} aria-label={`Ajustar ${item.nombre}`}>Ajustar</button>
                          <span className="inv-row-actions-sep" aria-hidden="true" />
                          <button className="btn btn-outline btn-sm" type="button" onClick={() => setModal({ clase: "historial", item })} aria-label={`Historial de ${item.nombre}`}>Historial</button>
                          <button className="btn btn-outline btn-sm" type="button" onClick={() => setModal({ clase: "producto", item })} aria-label={`Editar ${item.nombre}`}>Editar</button>
                          <button className="btn btn-outline btn-sm inv-delete" type="button" onClick={() => eliminar(item)} aria-label={`Eliminar ${item.nombre}`}>Eliminar</button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}

          {pestana === "movimientos" && (
            <div className="inv-movs-layout" id="inv-panel-movimientos" role="tabpanel" aria-labelledby="inv-tab-movimientos">
              <section className="card inv-section" aria-labelledby="inv-feed-titulo">
                <h2 id="inv-feed-titulo">Últimos movimientos</h2>
                <div className="inv-filters inv-filters-short">
                  <div className="form-field">
                    <label htmlFor="inv-filtro-tipo">Tipo</label>
                    <select id="inv-filtro-tipo" value={filtroTipo} onChange={(event) => setFiltroTipo(event.target.value)}>
                      <option value="">Todos</option>
                      {Object.entries(TIPOS_MOVIMIENTO).map(([clave, datos]) => <option key={clave} value={clave}>{datos.etiqueta}</option>)}
                    </select>
                  </div>
                  <div className="form-field">
                    <label htmlFor="inv-filtro-evento">Evento</label>
                    <select id="inv-filtro-evento" value={filtroEvento} onChange={(event) => setFiltroEvento(event.target.value)}>
                      <option value="">Todos</option>
                      {eventos.map((evento) => <option key={evento.id} value={evento.id}>{evento.nombre}</option>)}
                    </select>
                  </div>
                </div>
                {errorMovimientos ? <p className="inv-form-error" role="alert">{errorMovimientos}</p>
                  : movimientos === null ? <p className="inv-empty">Cargando movimientos…</p>
                  : movimientos.length === 0 ? <p className="inv-empty">No hay movimientos con esos filtros.</p>
                  : <ul className="inv-mov-list">{movimientos.map((mov) => <FilaMovimiento key={mov.id} mov={mov} nombresEventos={nombresEventos} mostrarProducto />)}</ul>}
              </section>

              <section className="card inv-section" aria-labelledby="inv-evento-titulo">
                <h2 id="inv-evento-titulo">Consumo por evento</h2>
                <div className="form-field">
                  <label htmlFor="inv-consumo-evento">Evento</label>
                  <select id="inv-consumo-evento" value={eventoConsumo} onChange={(event) => elegirEventoConsumo(event.target.value)}>
                    <option value="">Selecciona un evento…</option>
                    {eventos.map((evento) => <option key={evento.id} value={evento.id}>{evento.nombre}{evento.fecha ? ` · ${fechaEvento(evento.fecha)}` : ""}</option>)}
                  </select>
                </div>
                {errorConsumo ? <p className="inv-form-error" role="alert">{errorConsumo}</p>
                  : cargandoConsumo ? <p className="inv-empty">Consultando consumo…</p>
                  : !eventoConsumo ? <p className="inv-empty">Elige un evento para ver qué productos se consumieron.</p>
                  : consumo && consumo.length === 0 ? <p className="inv-empty">No hay consumos ni salidas registrados para este evento.</p>
                  : consumo && (
                    <ul className="inv-consumo-list">
                      {consumo.map((fila) => <li key={fila.item_id}><span>{fila.nombre}</span><strong>{cantidadTexto(fila.cantidad)} {fila.unidad}</strong></li>)}
                    </ul>
                  )}
              </section>
            </div>
          )}
        </>
      )}

      <div className="inv-toast-region" role="status">
        {exito && <div className="inv-toast">{exito}</div>}
      </div>

      {modal?.clase === "movimiento" && (
        <ModalMovimiento item={modal.item} tipoInicial={modal.tipo} cantidadInicial={modal.cantidad} eventos={eventos} onClose={() => setModal(null)} onGuardado={alRegistrarMovimiento} />
      )}
      {modal?.clase === "producto" && (
        <ModalProducto item={modal.item} categorias={categorias} onClose={() => setModal(null)} onGuardado={alGuardarProducto} />
      )}
      {modal?.clase === "historial" && (
        <ModalHistorial item={modal.item} nombresEventos={nombresEventos} onClose={() => setModal(null)} />
      )}
    </div>
  );
}
