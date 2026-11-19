"""Generación de imágenes QR en el servidor (SVG y PNG) con la librería ``segno``."""

from __future__ import annotations

import io

import segno

COLOR_OSCURO = "#07101e"
COLOR_CLARO = "#ffffff"


def renderizar_qr(contenido: str, formato_imagen: str = "svg", *, escala: int = 10) -> tuple[bytes, str]:
    """Devuelve ``(bytes, media_type)`` del QR para ``contenido``."""
    qr = segno.make(contenido, error="m", micro=False)
    salida = io.BytesIO()
    if formato_imagen == "svg":
        qr.save(salida, kind="svg", scale=escala, border=2, dark=COLOR_OSCURO, light=COLOR_CLARO, xmldecl=False)
        return salida.getvalue(), "image/svg+xml"
    if formato_imagen == "png":
        qr.save(salida, kind="png", scale=escala, border=2, dark=COLOR_OSCURO, light=COLOR_CLARO)
        return salida.getvalue(), "image/png"
    raise ValueError("Formato de imagen no soportado.")
