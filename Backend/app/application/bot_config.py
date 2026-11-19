"""Configuración editable del asistente (guardada en base de datos, con valores por defecto)."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.infrastructure.models.bot_configuracion_model import BotConfiguracionModel

# clave -> (valor por defecto, descripción corta, tipo)
DEFINICION: dict[str, tuple[str, str, str]] = {
    "bot_activo": ("true", "Asistente activo en la web y en WhatsApp", "bool"),
    "ia_habilitada": ("true", "Usar la IA (Gemini) cuando esté configurada", "bool"),
    "nombre_bot": ("Medi", "Nombre con el que se presenta el asistente", "texto"),
    "saludo": (
        "¡Hola! Soy Medi, el asistente de Medallo Club. Puedo mostrarte los próximos eventos, "
        "ayudarte a reservar una mesa o un palco y resolver tus dudas.",
        "Mensaje de bienvenida",
        "texto",
    ),
    "horario": ("Jueves a sábado, de 8:00 p. m. a 3:00 a. m.", "Horario de atención del club", "texto"),
    "direccion": ("Provenza, Medellín, Colombia", "Dirección del club", "texto"),
    "dress_code": ("Casual elegante. El club se reserva el derecho de admisión.", "Código de vestimenta", "texto"),
    "edad_minima": ("18", "Edad mínima de ingreso", "entero"),
    "politica_reservas": (
        "Una reserva queda garantizada cuando el equipo la confirma: recibes un código de "
        "garantía y un pase QR por persona. Llega antes de la hora límite indicada.",
        "Política de reservas",
        "texto",
    ),
    "info_precios": (
        "El consumo mínimo depende del evento y de la ubicación (mesa o palco); el equipo te lo "
        "confirma al garantizar tu reserva.",
        "Respuesta sobre precios y consumo mínimo",
        "texto",
    ),
    "hora_limite_defecto": ("23:30", "Hora límite de llegada por defecto (HH:MM)", "hora"),
    "contacto_equipo": ("", "Contacto humano que se comparte con clientes molestos", "texto"),
    "escalar_negativos": ("true", "Avisar al equipo cuando un cliente expresa molestia", "bool"),
    "ia_limite_diario": ("200", "Máximo de consultas diarias a la IA", "entero"),
}


def _validar(clave: str, valor: str) -> str:
    _, _, tipo = DEFINICION[clave]
    valor = (valor or "").strip()
    if tipo == "bool":
        if valor.lower() not in ("true", "false"):
            raise ValidationError(f"«{clave}» debe ser verdadero o falso.")
        return valor.lower()
    if tipo == "entero":
        if not valor.isdigit() or not (1 <= int(valor) <= 100000):
            raise ValidationError(f"«{clave}» debe ser un número entero positivo.")
        return str(int(valor))
    if tipo == "hora":
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", valor):
            raise ValidationError(f"«{clave}» debe tener formato HH:MM.")
        return valor
    if len(valor) > 600:
        raise ValidationError(f"«{clave}» no puede superar 600 caracteres.")
    return valor


def obtener_config(db: Session) -> dict[str, str]:
    guardados = {fila.clave: fila.valor for fila in db.execute(select(BotConfiguracionModel)).scalars()}
    return {clave: guardados.get(clave, defecto) for clave, (defecto, _, _) in DEFINICION.items()}


def actualizar_config(db: Session, cambios: dict[str, str | bool | int]) -> dict[str, str]:
    desconocidas = [clave for clave in cambios if clave not in DEFINICION]
    if desconocidas:
        raise ValidationError(f"Parámetros desconocidos: {', '.join(desconocidas)}.")
    for clave, valor in cambios.items():
        texto = str(valor).lower() if isinstance(valor, bool) else str(valor)
        limpio = _validar(clave, texto)
        fila = db.get(BotConfiguracionModel, clave)
        if fila is None:
            db.add(BotConfiguracionModel(clave=clave, valor=limpio))
        else:
            fila.valor = limpio
    db.commit()
    return obtener_config(db)


def es_verdadero(config: dict[str, str], clave: str) -> bool:
    return config.get(clave, DEFINICION[clave][0]).lower() == "true"


def metadatos() -> list[dict[str, str]]:
    return [
        {"clave": clave, "descripcion": descripcion, "tipo": tipo, "defecto": defecto}
        for clave, (defecto, descripcion, tipo) in DEFINICION.items()
    ]
