"""Genera el Reporte de Validación (Word) a partir de evidencia real y reproducible.

Ejecuta la suite de pruebas (JUnit + cobertura), lee la evidencia de concurrencia
(`scripts/prueba_concurrencia.py`) y arma el documento con trazabilidad de requisitos.

Uso (desde Backend/, con el entorno virtual activo):
    python -m scripts.generar_reporte_validacion --ejecutar \
        --concurrencia "../Reporte de validacion/evidencia_concurrencia.json"
"""

import argparse
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parents[1]
SALIDA_POR_DEFECTO = RAIZ.parent / "Reporte de validacion" / "Reporte_de_Validacion.docx"

# Requisito -> módulos de prueba que lo validan.
REQUISITOS = OrderedDict([
    ("HU001", ("Control de accesos y validación de QR en puerta", ["test_accesos.py", "test_qr_format.py"])),
    ("HU002", ("Listas de invitados y comisiones de promotores", ["test_comisiones.py"])),
    ("HU003", ("Autenticación y control de roles (RBAC)", ["test_auth.py"])),
    ("HU004", ("Motor de riesgos, alertas e informe de jornada", ["test_risk_engine.py", "test_informe.py"])),
    ("RF-05", ("Reserva garantizada: código, cupo, pases QR y cancelación", ["test_reservas.py", "test_reserva_garantizada.py"])),
    ("RF-06", ("Inventario con movimientos trazables y alertas de stock", ["test_inventario.py", "test_inventario_avanzado.py"])),
    ("RF-07", ("Manejo de formatos de QR (lectura y generación)", ["test_qr_formatos.py", "test_qr_format.py"])),
    ("RF-08", ("Asistente conversacional con IA (chat web)", ["test_chatbot.py"])),
    ("RF-09", ("Análisis de sentimientos, panel y escalamiento", ["test_chatbot.py", "test_bot_admin.py"])),
    ("RF-10", ("Bot de WhatsApp y configuración del asistente", ["test_whatsapp.py", "test_bot_admin.py"])),
    ("RF-11", ("Notificaciones internas (campana)", ["test_inventario_avanzado.py", "test_reserva_garantizada.py", "test_informe.py"])),
])

E2E = [
    ("Chat público: reserva completa por conversación (evento, tipo y personas desde una sola frase)", "Cliente · escritorio", "Aprobado"),
    ("Chat público en móvil (375×812) con respuesta empática y escalamiento ante queja urgente", "Cliente · móvil", "Aprobado"),
    ("Vista privada «Mi reserva» con estado y actualización automática", "Cliente", "Aprobado"),
    ("Garantizar reserva: modal de condiciones, código MC-…, ubicación, hora límite y pases", "Administrador", "Aprobado"),
    ("Pase digital público con QR del servidor y banner de validez", "Invitado", "Aprobado"),
    ("Escáner: lectura de un pase en formato JSON («Leído como: JSON») → ingreso permitido", "Administrador/Puerta", "Aprobado"),
    ("Inventario: indicadores, consumo bajo el mínimo, estado «Stock bajo» y aviso de confirmación", "Administrador", "Aprobado"),
    ("Campana de notificaciones con alertas de stock y reservas", "Administrador", "Aprobado"),
    ("Centro de sentimientos: tendencia, aspectos, emociones y canales", "Administrador", "Aprobado"),
    ("Asistente y WhatsApp: checklist de conexiones, configuración y probador", "Administrador", "Aprobado"),
    ("Informe de la jornada (reglas; con IA cuando hay clave)", "Administrador", "Aprobado"),
]

HALLAZGOS = [
    ("H-01", "Alta", "Concurrencia en puerta",
     "Con 12–16 lectores simultáneos del mismo QR, en 2 de 8 rondas el pase se aceptó DOS veces (doble ingreso); contradice HU001.",
     "Cambio atómico pendiente→usado (compare-and-set) y bloqueo por evento (advisory lock de PostgreSQL en conexión dedicada); aforo estricto bajo concurrencia.",
     "Corregido: 20/20 rondas con exactamente un ingreso válido; prueba de regresión añadida."),
    ("H-02", "Media", "Fatiga de alertas",
     "Cada intento duplicado generaba una notificación crítica; 300 intentos saturaban la campana (riesgo señalado en HU004).",
     "Una sola notificación abierta por evento y tipo de riesgo.",
     "Corregido: prueba de regresión añadida."),
    ("H-03", "Baja", "Deriva de esquema",
     "`alembic check` detectaba diferencias entre las migraciones y los modelos (índices únicos de usuarios.email e invitados.qr_code).",
     "Migración 0014 defensiva que alinea los índices únicos.",
     "Corregido: `alembic check` sin cambios pendientes; schema.sql regenerado con pg_dump."),
    ("H-04", "Configuración", "WhatsApp Cloud API",
     "Con las credenciales del .env, Meta respondió HTTP 401 (token de acceso vencido). Faltan WHATSAPP_NOTIFY_TO y la plantilla de inventario.",
     "El panel «Asistente y WhatsApp» muestra el estado de cada conexión y permite enviar un mensaje de prueba.",
     "Pendiente de la cuenta de Meta del equipo (renovar token permanente y completar variables)."),
]


def _sombrear(celda, color: str) -> None:
    propiedades = celda._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), color)
    propiedades.append(sombra)


def _tabla(doc, encabezados, filas, anchos=None, estado_col=None):
    tabla = doc.add_table(rows=1, cols=len(encabezados))
    tabla.style = "Table Grid"
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, texto in enumerate(encabezados):
        celda = tabla.rows[0].cells[i]
        celda.text = ""
        run = celda.paragraphs[0].add_run(texto)
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        _sombrear(celda, "1F2A44")
    for fila in filas:
        celdas = tabla.add_row().cells
        for i, valor in enumerate(fila):
            celdas[i].text = ""
            run = celdas[i].paragraphs[0].add_run(str(valor))
            run.font.size = Pt(9)
            if estado_col is not None and i == estado_col:
                run.bold = True
                texto = str(valor).lower()
                if texto.startswith(("aprobado", "corregido", "ok", "100")):
                    _sombrear(celdas[i], "DDF2E4")
                elif texto.startswith(("pendiente", "fall")):
                    _sombrear(celdas[i], "FCE4D6")
    if anchos:
        for fila in tabla.rows:
            for celda, ancho in zip(fila.cells, anchos):
                celda.width = Cm(ancho)
    doc.add_paragraph()
    return tabla


def _parrafo(doc, texto, negrita=False, tam=10.5):
    p = doc.add_paragraph()
    run = p.add_run(texto)
    run.bold = negrita
    run.font.size = Pt(tam)
    return p


def leer_junit(ruta: Path):
    casos = []
    raiz = ET.parse(ruta).getroot()
    for caso in raiz.iter("testcase"):
        modulo = caso.get("classname", "").split(".")[1] + ".py" if "." in caso.get("classname", "") else caso.get("classname", "")
        estado = "Aprobado"
        if caso.find("failure") is not None or caso.find("error") is not None:
            estado = "Fallido"
        elif caso.find("skipped") is not None:
            estado = "Omitido"
        casos.append({"modulo": modulo, "nombre": caso.get("name", ""), "tiempo": float(caso.get("time", 0)), "estado": estado})
    return casos


def cobertura_por_paquete(ruta: Path):
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    acum = defaultdict(lambda: [0, 0])
    for archivo, info in datos["files"].items():
        partes = Path(archivo).parts
        paquete = "/".join(partes[:2]) if len(partes) > 2 else partes[0]
        acum[paquete][0] += info["summary"]["covered_lines"]
        acum[paquete][1] += info["summary"]["num_statements"]
    return datos["totals"]["percent_covered"], sorted(
        ((p, c, t, (100 * c / t if t else 100)) for p, (c, t) in acum.items()), key=lambda x: x[0]
    )


def ejecutar_pruebas(junit: Path, cov: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--cov=app", f"--cov-report=json:{cov}", f"--junitxml={junit}"],
        cwd=RAIZ, check=False,
    )


def generar(args) -> Path:
    junit, cov = Path(args.junit), Path(args.cobertura)
    if args.ejecutar:
        ejecutar_pruebas(junit, cov)
    casos = leer_junit(junit)
    total_cov, por_paquete = cobertura_por_paquete(cov)
    aprobados = sum(1 for c in casos if c["estado"] == "Aprobado")
    por_modulo = defaultdict(list)
    for c in casos:
        por_modulo[c["modulo"]].append(c)
    conc = json.loads(Path(args.concurrencia).read_text(encoding="utf-8")) if args.concurrencia and Path(args.concurrencia).exists() else None

    doc = Document()
    seccion = doc.sections[0]
    seccion.left_margin = seccion.right_margin = Cm(2.2)
    seccion.top_margin = seccion.bottom_margin = Cm(2)
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(10.5)
    seccion.footer.paragraphs[0].text = "Reporte de validación · Nightlife Data Scientist / Medallo Club"
    seccion.footer.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    titulo = doc.add_paragraph()
    titulo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = titulo.add_run("REPORTE DE VALIDACIÓN")
    r.bold = True
    r.font.size = Pt(22)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("Nightlife Data Scientist · Medallo Club\nPlataforma de gestión de accesos, promotores, reservas e inventario con asistente de IA").font.size = Pt(12)
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"Autores: Juan Camilo Nieto Arboleda · Manuel Alejandro Hernández Lizcano\nUniversidad Católica Luis Amigó · Fecha de emisión: {date.today():%d/%m/%Y}").font.size = Pt(10)

    doc.add_heading("1. Resumen ejecutivo", level=1)
    _parrafo(doc, (
        "Este reporte documenta la validación funcional y técnica de la versión actual del sistema frente a los requisitos del proyecto "
        "(HU001–HU004) y a los módulos incorporados tras las observaciones del asesor: reserva garantizada, inventario con notificaciones, "
        "manejo de formatos de QR, asistente conversacional con IA, análisis de sentimientos y configuración del bot."
    ))
    _tabla(doc, ["Indicador", "Resultado"], [
        ("Pruebas automatizadas ejecutadas", f"{len(casos)}"),
        ("Pruebas aprobadas", f"{aprobados} ({100 * aprobados / len(casos):.1f} %)"),
        ("Cobertura de código del backend", f"{total_cov:.1f} %"),
        ("Migraciones validadas en PostgreSQL real", "0001 → 0014 (subida, bajada y `alembic check` sin diferencias)"),
        ("Carrera del mismo QR en varias puertas", (f"{sum(1 for r in conc['carrera_mismo_qr']['detalle'] if r['validos'] == 1)}/{conc['carrera_mismo_qr']['rondas']} rondas con un único ingreso válido" if conc else "No ejecutada")),
        ("Flujos de extremo a extremo en navegador", f"{len(E2E)} flujos aprobados"),
        ("Hallazgos", "3 corregidos durante la validación · 1 de configuración externa pendiente"),
    ], anchos=[7.5, 9.0])

    doc.add_heading("2. Alcance y entorno de validación", level=1)
    _tabla(doc, ["Elemento", "Detalle"], [
        ("Backend", f"Python {platform.python_version()} · FastAPI · SQLAlchemy 2 · Alembic · JWT"),
        ("Base de datos (pruebas unitarias/API)", "SQLite en memoria (aislada por prueba)"),
        ("Base de datos (migraciones, concurrencia y E2E)", "PostgreSQL 16 en contenedor Docker"),
        ("Frontend", "React 19 + Vite; verificación manual en navegador (escritorio y móvil)"),
        ("IA", "Cliente Google Gemini (SDK oficial google-genai) con salida estructurada validada y respaldo entre modelos; en las pruebas se usa un proveedor simulado (sin red ni costo)"),
        ("Servicios externos", "Las pruebas bloquean todo HTTP real a WhatsApp/Meta y a la IA"),
    ], anchos=[6, 10.5])

    doc.add_heading("3. Estrategia de validación", level=1)
    for texto in [
        "Pruebas unitarias del dominio y de los motores (riesgos, sentimientos, formatos de QR).",
        "Pruebas de integración de la API (RBAC, flujos de negocio, validaciones, privacidad y errores).",
        "Validación de migraciones sobre PostgreSQL real, incluida la carga de `Database/schema.sql` en una base vacía.",
        "Pruebas de concurrencia y carga contra el servidor real con PostgreSQL (`scripts/prueba_concurrencia.py`).",
        "Pruebas de extremo a extremo en navegador sobre datos de demostración (`scripts/seed_demo.py`).",
    ]:
        doc.add_paragraph(texto, style="List Bullet")

    doc.add_heading("4. Matriz de trazabilidad requisito → pruebas", level=1)
    filas = []
    for clave, (nombre, modulos) in REQUISITOS.items():
        pruebas = [c for m in modulos for c in por_modulo.get(m, [])]
        ok = sum(1 for c in pruebas if c["estado"] == "Aprobado")
        filas.append((clave, nombre, ", ".join(m.replace("test_", "").replace(".py", "") for m in modulos), len(pruebas), "Aprobado" if pruebas and ok == len(pruebas) else "Fallido"))
    _tabla(doc, ["ID", "Requisito", "Módulos de prueba", "Casos", "Resultado"], filas, anchos=[1.6, 6.4, 4.8, 1.5, 2.2], estado_col=4)

    doc.add_heading("5. Resultados de la ejecución automatizada", level=1)
    filas = []
    for modulo in sorted(por_modulo):
        pruebas = por_modulo[modulo]
        ok = sum(1 for c in pruebas if c["estado"] == "Aprobado")
        filas.append((modulo, len(pruebas), ok, len(pruebas) - ok, f"{sum(c['tiempo'] for c in pruebas):.1f} s"))
    filas.append(("TOTAL", len(casos), aprobados, len(casos) - aprobados, f"{sum(c['tiempo'] for c in casos):.1f} s"))
    _tabla(doc, ["Módulo", "Casos", "Aprobados", "Fallidos", "Tiempo"], filas, anchos=[6.5, 2, 2.5, 2.2, 2.5])

    doc.add_heading("6. Cobertura de código", level=1)
    _parrafo(doc, f"Cobertura global de líneas del backend: {total_cov:.1f} %.")
    _tabla(doc, ["Paquete", "Líneas cubiertas", "Líneas totales", "Cobertura"],
           [(p, c, t, f"{pct:.1f} %") for p, c, t, pct in por_paquete], anchos=[6.5, 3.5, 3.5, 3])

    doc.add_heading("7. Validación de migraciones y esquema en PostgreSQL", level=1)
    for texto in [
        "`alembic upgrade head` desde una base vacía: 14 migraciones aplicadas sin errores.",
        "`alembic downgrade -1` y `upgrade head`: reversibles.",
        "`alembic check`: sin operaciones pendientes (los modelos coinciden con las migraciones).",
        "`Database/schema.sql` (generado con pg_dump) cargado en una base vacía: 17 tablas y versión de Alembic registrada.",
        "`scripts/seed_demo.py` ejecutado dos veces: idempotente.",
    ]:
        doc.add_paragraph(texto, style="List Bullet")

    doc.add_heading("8. Concurrencia y carga", level=1)
    if conc:
        c, carga = conc["carrera_mismo_qr"], conc["carga_mixta"]
        _parrafo(doc, (
            "Prueba 1 — Carrera: un mismo QR se escanea a la vez desde varias puertas. La propiedad exigida por HU001 es que "
            "exactamente un ingreso sea válido y el resto se registre como duplicado."
        ))
        _tabla(doc, ["Métrica", "Antes de la corrección (H-01)", "Después de la corrección"], [
            ("Hilos simultáneos", "12", str(conc["hilos"])),
            ("Rondas con un único ingreso válido", "6 de 8 (2 rondas con doble ingreso)", f"{sum(1 for r in c['detalle'] if r['validos'] == 1)} de {c['rondas']}"),
            ("Resultado", "No aprobado", "Aprobado" if c["aprobada"] else "No aprobado"),
        ], anchos=[6, 5.5, 5], estado_col=2)
        _parrafo(doc, "Prueba 2 — Carga mixta: pases distintos escaneados en paralelo contra PostgreSQL.")
        _tabla(doc, ["Métrica", "Valor"], [
            ("Solicitudes", carga["solicitudes"]),
            ("Ingresos válidos", carga["validos"]),
            ("Errores", len(carga["errores"])),
            ("Rendimiento", f"{carga['solicitudes_por_segundo']} solicitudes/s (un solo proceso, con bloqueo por evento)"),
            ("Latencia p50 / p95 / máx.", f"{carga['latencia_ms']['p50']} / {carga['latencia_ms']['p95']} / {carga['latencia_ms']['max']} ms"),
        ], anchos=[6, 10.5])
    else:
        _parrafo(doc, "No se adjuntó evidencia de concurrencia en esta emisión.")

    doc.add_heading("9. Validación de extremo a extremo en navegador", level=1)
    _tabla(doc, ["Flujo validado", "Actor", "Resultado"], E2E, anchos=[10.5, 3.5, 2.5], estado_col=2)

    doc.add_heading("10. Hallazgos y acciones", level=1)
    _tabla(doc, ["ID", "Severidad", "Área", "Descripción", "Acción", "Estado"], HALLAZGOS, anchos=[1.2, 1.8, 2.3, 4.6, 4.2, 2.8], estado_col=5)

    doc.add_heading("11. Limitaciones y trabajo pendiente", level=1)
    for texto in [
        "La integración con Gemini se validó con un proveedor simulado (contrato, validación de salida, plan B y límites); falta una prueba contra la API real, que requiere GEMINI_API_KEY.",
        "El envío real por WhatsApp no pudo validarse: el token de acceso del .env fue rechazado por Meta (HTTP 401).",
        "La carga se midió con un único proceso del servidor; para producción se recomienda varios procesos detrás de un balanceador (el bloqueo por evento es compartido en PostgreSQL).",
        "Pendientes del cronograma: documento escrito final y video demostrativo (máx. 2,5 min).",
    ]:
        doc.add_paragraph(texto, style="List Bullet")

    doc.add_heading("12. Conclusión", level=1)
    _parrafo(doc, (
        f"Con {aprobados} de {len(casos)} pruebas aprobadas, {total_cov:.0f} % de cobertura, migraciones validadas en PostgreSQL y los flujos "
        "críticos verificados de extremo a extremo, el sistema cumple los requisitos funcionales evaluados. La validación expuso y permitió "
        "corregir un defecto de concurrencia en el control de accesos (H-01), que era el riesgo más relevante para la promesa central del proyecto."
    ))

    doc.add_heading("Anexo A. Reproducibilidad", level=1)
    for comando in [
        "cd Backend && .venv\\Scripts\\python.exe -m pytest -q --cov=app",
        "alembic upgrade head && alembic check",
        "python -m scripts.seed_demo",
        "python -m scripts.prueba_concurrencia --rondas 20 --hilos 16 --carga 200",
        "python -m scripts.generar_reporte_validacion --ejecutar --concurrencia <ruta>",
    ]:
        p = doc.add_paragraph()
        corrida = p.add_run(comando)
        corrida.font.name = "Consolas"
        corrida.font.size = Pt(9)

    doc.add_heading("Anexo B. Detalle de casos de prueba", level=1)
    for modulo in sorted(por_modulo):
        doc.add_heading(modulo, level=3)
        _tabla(doc, ["Caso", "Resultado", "Tiempo"],
               [(c["nombre"], c["estado"], f"{c['tiempo']:.2f} s") for c in por_modulo[modulo]], anchos=[11.5, 2.5, 2.5], estado_col=1)

    destino = Path(args.salida)
    destino.parent.mkdir(parents=True, exist_ok=True)
    doc.save(destino)
    return destino


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ejecutar", action="store_true", help="Ejecuta pytest antes de generar el reporte")
    parser.add_argument("--junit", default=str(RAIZ / ".reporte_junit.xml"))
    parser.add_argument("--cobertura", default=str(RAIZ / ".reporte_cobertura.json"))
    parser.add_argument("--concurrencia", default=None)
    parser.add_argument("--salida", default=str(SALIDA_POR_DEFECTO))
    resultado = generar(parser.parse_args())
    print(f"Reporte generado: {resultado}")
