"""Análisis de sentimientos en español (motor local, explicable y sin dependencias).

Es el motor de respaldo del asistente: funciona sin conexión y sin costo, y entrega
resultados interpretables (qué palabras pesaron). Cuando hay un proveedor de IA
configurado, el asistente lo usa para refinar el resultado; este módulo sigue siendo la
base de comparación y el plan B si el proveedor falla.

Qué detecta: polaridad (con negaciones, intensificadores, contraste con «pero», emojis y
jerga colombiana), emoción dominante, intensidad, aspectos del negocio (servicio, precio,
música, seguridad…) con su propio sentimiento, y señales de urgencia que requieren
atención humana (fraude, acoso, agresiones, cobros indebidos…).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import defaultdict

METODO_LOCAL = "Léxico español explicable v2 (aspectos, emociones y urgencia)"


def sin_tildes(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _normalizar(texto: str) -> str:
    return sin_tildes(texto.casefold())


# --- Léxico (claves sin tildes) -------------------------------------------------------

POSITIVAS: dict[str, float] = {
    "excelente": 1.5, "espectacular": 1.5, "genial": 1.3, "increible": 1.4, "maravilloso": 1.4,
    "maravillosa": 1.4, "perfecto": 1.4, "perfecta": 1.4, "bacano": 1.2, "bacana": 1.2,
    "chimba": 1.3, "chimbita": 1.2, "brutal": 1.1, "delicia": 1.2, "fino": 0.9, "top": 1.0,
    "lindo": 1.0, "linda": 1.0, "hermoso": 1.0, "hermosa": 1.0, "bueno": 0.8, "buena": 0.8,
    "buenos": 0.8, "buenas": 0.8, "buenisimo": 1.3, "buenisima": 1.3, "rico": 0.9, "rica": 0.9,
    "agradable": 0.9, "amable": 1.0, "amables": 1.0, "rapido": 0.8, "rapida": 0.8,
    "facil": 0.7, "limpio": 0.8, "limpia": 0.8, "divertido": 1.0, "divertida": 1.0,
    "recomiendo": 1.1, "recomendado": 1.0, "recomendable": 1.0, "feliz": 1.1, "contento": 1.0,
    "contenta": 1.0, "encanta": 1.3, "encanto": 1.2, "encantado": 1.2, "encantada": 1.2,
    "gracias": 0.6, "volveria": 1.2, "volvere": 1.2, "mejor": 1.0, "atento": 0.9,
    "atenta": 0.9, "atentos": 0.9, "puntual": 0.8, "organizado": 0.9, "organizada": 0.9,
    "genios": 1.0, "crack": 1.0, "disfrute": 1.0, "disfrutamos": 1.0, "gusto": 0.7,
    "excelentes": 1.5, "geniales": 1.3, "felicitaciones": 1.1, "satisfecho": 1.1,
    "satisfecha": 1.1, "comodo": 0.8, "comoda": 0.8, "seguro": 0.5, "wow": 1.2,
}
NEGATIVAS: dict[str, float] = {
    "malo": 1.0, "mala": 1.0, "malos": 1.0, "malas": 1.0, "terrible": 1.4, "horrible": 1.5,
    "pesimo": 1.6, "pesima": 1.6, "desastre": 1.5, "maluco": 0.9, "maluca": 0.9,
    "mamera": 1.0, "caro": 0.9, "cara": 0.9, "caros": 0.9, "caras": 0.9, "carisimo": 1.3,
    "carisima": 1.3, "carisimos": 1.3, "carisimas": 1.3, "demora": 1.0, "demorado": 1.0, "demorada": 1.0, "demoraron": 1.0,
    "lento": 0.9, "lenta": 0.9, "problema": 0.9, "problemas": 0.9, "queja": 1.0,
    "quejas": 1.0, "cancelado": 0.8, "cancelada": 0.8, "molesto": 1.1, "molesta": 1.1,
    "triste": 1.0, "decepcionado": 1.2, "decepcionada": 1.2, "decepcionante": 1.2,
    "sucio": 1.2, "sucia": 1.2, "estafa": 1.7, "fraude": 1.7, "robo": 1.4, "robaron": 1.6,
    "incomodo": 1.0, "incomoda": 1.0, "aburrido": 0.9, "aburrida": 0.9, "grosero": 1.4,
    "grosera": 1.4, "groseros": 1.4, "mal": 0.9, "peor": 1.3, "inseguro": 1.3, "insegura": 1.3,
    "peligro": 1.2, "peligroso": 1.2, "pelea": 1.0, "ruido": 0.5, "espera": 0.6,
    "esperar": 0.6, "tardaron": 0.9, "tarde": 0.4, "error": 0.8, "fallo": 0.8, "fallaron": 0.9,
    "inaceptable": 1.5, "indignante": 1.5, "vergonzoso": 1.3, "enojado": 1.2, "enojada": 1.2,
    "furioso": 1.4, "furiosa": 1.4, "pena": 0.5, "lastima": 0.8, "abuso": 1.4, "abusivo": 1.4,
    "ineficiente": 1.1, "desorganizado": 1.1, "desorganizada": 1.1, "desorden": 1.0,
    "irrespeto": 1.3, "irrespetuoso": 1.3, "acoso": 1.5, "agresivo": 1.3, "agredieron": 1.6,
}
FRASES: dict[str, float] = {
    "no volveria": -1.6, "no volvere": -1.6, "nunca mas": -1.5, "la mejor": 1.5,
    "lo mejor": 1.3, "de lujo": 1.2, "un lujo": 1.2, "mil gracias": 1.0, "muy bien": 1.0,
    "mal servicio": -1.5, "mala atencion": -1.5, "buena atencion": 1.3, "buen servicio": 1.3,
    "cobro de mas": -1.5, "cobraron de mas": -1.7, "me cobraron mal": -1.5,
    "no funciono": -1.2, "no llego": -1.0, "no me confirmaron": -1.2, "sin respuesta": -1.1,
    "nadie respondio": -1.2, "no contestan": -1.1, "perdi mi reserva": -1.5,
    "me quede esperando": -1.2, "todo bien": 0.9, "todo perfecto": 1.4,
}
EMOJIS: dict[str, float] = {
    "😍": 1.3, "😊": 1.0, "😀": 1.0, "😁": 1.0, "🥳": 1.2, "👍": 0.9, "🔥": 1.0, "🎉": 1.0,
    "❤": 1.0, "💃": 0.8, "🙌": 0.9, "👏": 0.9, "🤩": 1.3, "😎": 0.8,
    "😡": -1.4, "😠": -1.3, "🤬": -1.6, "👎": -1.0, "😞": -1.0, "😢": -1.0, "😭": -1.0,
    "😤": -1.0, "🤮": -1.4, "🙄": -0.7, "😒": -0.8,
}
NEGADORES = {"no", "nunca", "jamas", "ni", "sin", "tampoco", "nada"}
INTENSIFICADORES = {
    "muy": 1.4, "super": 1.4, "demasiado": 1.3, "bastante": 1.2, "re": 1.2, "tan": 1.2,
    "totalmente": 1.3, "realmente": 1.2, "sumamente": 1.4, "extremadamente": 1.5,
}
ATENUADORES = {"algo": 0.7, "medio": 0.7, "ligeramente": 0.6}

EMOCIONES: dict[str, set[str]] = {
    "enojo": {
        "estafa", "fraude", "robo", "robaron", "grosero", "grosera", "groseros", "molesto",
        "molesta", "pesimo", "pesima", "horrible", "terrible", "desastre", "inaceptable",
        "indignante", "enojado", "enojada", "furioso", "furiosa", "abuso", "abusivo", "irrespeto",
        "irrespetuoso", "vergonzoso", "😡", "😠", "🤬", "😤",
    },
    "tristeza": {"triste", "decepcionado", "decepcionada", "decepcionante", "lastima", "pena", "😞", "😢", "😭"},
    "miedo": {"inseguro", "insegura", "peligro", "peligroso", "pelea", "acoso", "agredieron", "agresivo"},
    "alegria": {
        "feliz", "contento", "contenta", "encanta", "encanto", "encantado", "encantada", "chimba",
        "chimbita", "divertido", "divertida", "genial", "geniales", "disfrute", "disfrutamos",
        "bacano", "bacana", "satisfecho", "satisfecha", "😍", "😊", "😀", "😁", "🥳", "🎉", "🤩",
    },
    "sorpresa": {"increible", "wow", "espectacular", "maravilloso", "maravillosa", "brutal", "😮", "🤯"},
}

ASPECTOS: dict[str, set[str]] = {
    "servicio": {
        "atencion", "servicio", "mesero", "mesera", "meseros", "personal", "trato", "atendieron",
        "atendio", "barman", "bartender", "staff", "amable", "amables", "grosero", "grosera",
    },
    "precio": {"precio", "precios", "caro", "cara", "caros", "caras", "barato", "costo", "cobro", "cobraron", "cuenta", "cover", "tarifa", "carisimo", "carisima", "carisimos", "carisimas"},
    "musica": {"musica", "dj", "sonido", "volumen", "playlist", "cancion", "canciones", "ruido"},
    "ambiente": {"ambiente", "lugar", "decoracion", "ambientacion", "limpio", "sucio", "bano", "banos", "aire", "calor", "espacio", "aforo", "lleno"},
    "seguridad": {"seguridad", "vigilante", "vigilantes", "inseguro", "insegura", "pelea", "robo", "robaron", "requisa", "peligro", "acoso"},
    "reserva": {"reserva", "reservas", "reservar", "mesa", "palco", "confirmacion", "confirmaron", "confirmar"},
    "acceso": {"fila", "puerta", "entrada", "qr", "ingreso", "ingresar", "cola", "espera", "esperar", "demora", "demoraron", "demorado"},
    "bebidas": {"trago", "tragos", "bebida", "bebidas", "coctel", "cocteles", "licor", "botella", "comida", "cerveza", "hielo"},
}
NOMBRES_ASPECTO = {
    "servicio": "Servicio y atención", "precio": "Precios y cobros", "musica": "Música y sonido",
    "ambiente": "Ambiente y limpieza", "seguridad": "Seguridad", "reserva": "Reservas",
    "acceso": "Acceso y filas", "bebidas": "Bebidas y comida",
}

URGENCIA: dict[str, str] = {
    "estafa": "posible estafa", "fraude": "posible fraude", "robo": "robo", "robaron": "robo",
    "acoso": "acoso", "acosaron": "acoso", "agredieron": "agresión", "agresion": "agresión",
    "amenaza": "amenaza", "amenazaron": "amenaza", "denuncia": "denuncia", "denunciar": "denuncia",
    "abogado": "tema legal", "policia": "intervención policial", "intoxique": "salud",
    "intoxicacion": "salud", "drogaron": "seguridad personal", "droga": "seguridad personal",
}
FRASES_URGENCIA = ("cobro de mas", "cobraron de mas", "cobro indebido", "me cobraron mal", "menor de edad")

_SEPARADOR = re.compile(r"([.;,!?¡¿\n]+|\bpero\b|\baunque\b|\bsin embargo\b|\by\b)", re.IGNORECASE)
_PALABRA = re.compile(r"[a-z0-9ñü]+")


def _clasificar_etiqueta(puntaje: float) -> str:
    if puntaje >= 0.2:
        return "positivo"
    if puntaje <= -0.2:
        return "negativo"
    return "neutral"


def etiqueta_de(puntaje: float) -> str:
    return _clasificar_etiqueta(puntaje)


def _puntuar_clausula(
    original: str, normalizada: str
) -> tuple[float, list[tuple[str, float]], list[str]]:
    """Devuelve (suma, términos con peso, emociones) de una cláusula."""
    suma = 0.0
    terminos: list[tuple[str, float]] = []
    emociones: list[str] = []
    texto = f" {normalizada} "

    for frase, peso in FRASES.items():
        if f" {frase} " in texto:
            suma += peso
            terminos.append((frase, peso))
            texto = texto.replace(f" {frase} ", " ")
    for emoji, peso in EMOJIS.items():
        cantidad = original.count(emoji)
        if cantidad:
            suma += peso * min(cantidad, 3)
            terminos.append((emoji, peso))
            for emocion, claves in EMOCIONES.items():
                if emoji in claves:
                    emociones.append(emocion)

    palabras = _PALABRA.findall(texto)
    for i, palabra in enumerate(palabras):
        peso = POSITIVAS.get(palabra, 0.0) - NEGATIVAS.get(palabra, 0.0)
        if not peso:
            continue
        previas = palabras[max(0, i - 3):i]
        if any(p in NEGADORES for p in previas):
            peso = -peso * (0.8 if peso > 0 else 0.5)
        for p in previas:
            if p in INTENSIFICADORES:
                peso *= INTENSIFICADORES[p]
            elif p == "poco" and peso > 0:
                peso = -peso * 0.5  # «poco amable» expresa lo contrario de «amable»
            elif p in ATENUADORES:
                peso *= ATENUADORES[p]
        suma += peso
        terminos.append((palabra, peso))
        for emocion, claves in EMOCIONES.items():
            if palabra in claves:
                emociones.append(emocion)

    # Énfasis expresivo: signos de exclamación y palabras en mayúsculas.
    enfasis = 1.0
    if any(len(t) > 3 and t.isupper() for t in re.findall(r"[A-ZÁÉÍÓÚÑ]{2,}", original)):
        enfasis += 0.15
    return suma * enfasis, terminos, emociones


def analizar_sentimiento(texto: str) -> dict:
    original = texto.strip()
    if not original:
        original = "mensaje sin texto"

    partes = _SEPARADOR.split(original)
    clausulas: list[tuple[str, bool]] = []  # (texto, viene después de un contraste)
    contraste_pendiente = False
    for parte in partes:
        if parte is None:
            continue
        marca = _normalizar(parte).strip()
        if marca in {"pero", "aunque", "sin embargo"}:
            contraste_pendiente = True
            continue
        if marca == "y" or re.fullmatch(r"[.;,!?¡¿\n]+", parte):
            continue
        if parte.strip():
            clausulas.append((parte, contraste_pendiente))
            contraste_pendiente = False
    hay_contraste = any(despues for _, despues in clausulas)

    total = 0.0
    positivos: dict[str, float] = {}
    negativos: dict[str, float] = {}
    emociones: defaultdict[str, float] = defaultdict(float)
    por_aspecto: defaultdict[str, float] = defaultdict(float)
    aspectos_mencionados: set[str] = set()
    normalizado_completo = _normalizar(original)

    for indice, (clausula, despues_de_contraste) in enumerate(clausulas):
        normalizada = _normalizar(clausula)
        suma, terminos, emos = _puntuar_clausula(clausula, normalizada)
        if hay_contraste:
            suma *= 1.5 if despues_de_contraste else 0.6
        total += suma
        for termino, peso in terminos:
            destino = positivos if peso > 0 else negativos
            destino[termino] = max(destino.get(termino, 0.0), abs(peso))
        for emocion in emos:
            emociones[emocion] += 1.0
        palabras = set(_PALABRA.findall(normalizada))
        for aspecto, claves in ASPECTOS.items():
            if palabras & claves:
                aspectos_mencionados.add(aspecto)
                por_aspecto[aspecto] += suma

    if original.count("!") >= 2:
        total *= 1.2
    puntaje = round(math.tanh(total / 2.0), 2)
    etiqueta = _clasificar_etiqueta(puntaje)
    cantidad_terminos = len(positivos) + len(negativos)
    magnitud = abs(puntaje)
    intensidad = "alta" if magnitud >= 0.6 else "media" if magnitud >= 0.3 else "baja"

    permitidas = {
        "negativo": {"enojo", "tristeza", "miedo"},
        "positivo": {"alegria", "sorpresa"},
    }.get(etiqueta)
    candidatas = {e: v for e, v in emociones.items() if permitidas is None or e in permitidas}
    if candidatas:
        emocion = max(candidatas.items(), key=lambda par: par[1])[0]
    elif etiqueta == "negativo":
        emocion = "enojo" if intensidad == "alta" else "molestia"
    elif etiqueta == "positivo":
        emocion = "alegria" if intensidad != "baja" else "neutral"
    else:
        emocion = "neutral"

    aspectos = [
        {
            "aspecto": aspecto,
            "nombre": NOMBRES_ASPECTO[aspecto],
            "sentimiento": _clasificar_etiqueta(round(math.tanh(por_aspecto[aspecto] / 2.0), 2)),
        }
        for aspecto in sorted(aspectos_mencionados)
    ]

    palabras_texto = set(_PALABRA.findall(normalizado_completo))
    motivos = sorted({URGENCIA[p] for p in palabras_texto if p in URGENCIA})
    motivos += [f for f in FRASES_URGENCIA if f in normalizado_completo and f not in motivos]
    urgente = bool(motivos)

    return {
        "etiqueta": etiqueta,
        "puntaje": puntaje,
        "intensidad": intensidad,
        "emocion": emocion,
        "confianza": round(min(1.0, 0.3 + 0.2 * min(cantidad_terminos, 3) + 0.3 * magnitud), 2),
        "terminos_positivos": list(positivos),
        "terminos_negativos": list(negativos),
        "aspectos": aspectos,
        "urgente": urgente,
        "motivo_urgencia": ", ".join(motivos) if motivos else None,
        "metodo": METODO_LOCAL,
    }
