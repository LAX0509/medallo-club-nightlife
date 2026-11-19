"""Datos de demostración completos para la exposición (idempotente).

Crea (solo lo que falte) usuarios, eventos con flyers, invitados y accesos de una noche
pasada, reservas pendientes y garantizadas, inventario con movimientos y alertas, y
conversaciones del asistente con sentimientos, de modo que todos los paneles se vean vivos.

Uso (desde Backend/, con el entorno virtual activo y la base de datos migrada):
    python -m scripts.seed_demo
"""

import json
import random
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.application import inventario_service, reserva_service  # noqa: E402
from app.application.chatbot import estado_inicial  # noqa: E402
from app.application.invitado_service import generar_qr_code  # noqa: E402
from app.application.sentiment_service import analizar_sentimiento  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.infrastructure.database.session import Base, SessionLocal, engine  # noqa: E402
from app.infrastructure.models import (  # noqa: E402
    AccesoQRModel, AlertaRiesgoModel, ChatMensajeModel, ChatSesionModel, ComisionModel,
    EventoModel, InventarioItemModel, InvitadoModel, ReservaModel, UsuarioModel,
)

ALEATORIO = random.Random(2026)
FLYERS = Path(__file__).resolve().parents[1] / "uploads" / "flyers"


def _usuario(db, nombre, email, rol, clave, telefono):
    existente = db.execute(select(UsuarioModel).where(UsuarioModel.email == email)).scalar_one_or_none()
    if existente:
        return existente
    usuario = UsuarioModel(nombre=nombre, email=email, password_hash=hash_password(clave), rol=rol, telefono=telefono, estado=True)
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def _evento(db, admin, nombre, dias, aforo, tematica, estado="planeado", flyer=None):
    existente = db.execute(select(EventoModel).where(EventoModel.nombre == nombre)).scalar_one_or_none()
    if existente:
        return existente, False
    flyer_url = f"/uploads/flyers/{flyer}" if flyer and (FLYERS / flyer).exists() else None
    evento = EventoModel(
        administrador_id=admin.id, nombre=nombre, fecha=date.today() + timedelta(days=dias),
        aforo_maximo=aforo, estado=estado, tematica=tematica, flyer_url=flyer_url,
    )
    db.add(evento)
    db.commit()
    db.refresh(evento)
    return evento, True


def _invitados(db, evento, promotor, nombres, usados=0):
    creados = []
    for i, nombre in enumerate(nombres):
        inv = InvitadoModel(
            evento_id=evento.id, promotor_id=promotor.id, nombre=nombre,
            qr_code=generar_qr_code(evento.id), estado="usado" if i < usados else "pendiente",
        )
        db.add(inv)
        creados.append(inv)
    db.commit()
    return creados


NOMBRES = [
    "María Gómez", "Juan Pérez", "Laura Restrepo", "Andrés Cardona", "Valentina Ospina", "Camilo Torres",
    "Daniela Ríos", "Sebastián Vélez", "Manuela Arango", "Felipe Londoño", "Isabela Zapata", "Mateo Henao",
    "Sofía Jaramillo", "Santiago Mejía", "Luciana Uribe", "Nicolás Giraldo", "Mariana Cano", "Tomás Escobar",
    "Gabriela Montoya", "David Ramírez", "Natalia Quintero", "Julián Bedoya", "Paula Salazar", "Esteban Duque",
]

CONVERSACIONES = [
    ("Nos encantó la noche, la música estuvo chimba y la atención muy amable", 9),
    ("Excelente servicio, el mesero fue muy atento. Volveremos pronto", 8),
    ("La reserva fue rápida y fácil, todo perfecto, gracias", 8),
    ("El ambiente espectacular pero los tragos carísimos", 7),
    ("La fila para entrar fue eterna, una demora terrible en la puerta", 7),
    ("Me cobraron de más en la cuenta y nadie quiso corregirlo, qué mamera", 6),
    ("La música muy buena, el DJ es un crack 🔥", 6),
    ("No me confirmaron la reserva y nadie respondió mis mensajes", 5),
    ("Todo bien, solo quería saber el horario", 5),
    ("Pésima seguridad, hubo una pelea y nadie hizo nada, me sentí inseguro", 4),
    ("Buena atención y buen ambiente, recomendado", 4),
    ("El baño estaba sucio y hacía mucho calor, muy incómodo", 3),
    ("Me robaron el celular dentro del club, esto es una estafa", 2),
    ("Gracias por la reserva garantizada, súper organizados 😍", 2),
    ("Los precios son un poco altos pero la música lo vale", 1),
    ("Muy lento el servicio de bebidas, tardaron una eternidad", 1),
    ("Fue una noche increíble, mil gracias al equipo", 0),
    ("La reserva garantizada llegó al instante con mis pases, qué organización 👏", 6),
    ("Me encantó el ambiente y la atención, ya recomendé el club a mis amigos", 5),
    ("El DJ estuvo brutal y el servicio en la mesa muy rápido", 3),
    ("Excelente experiencia en el palco, todo perfecto", 3),
    ("Gracias, el personal de puerta fue amable y el ingreso con el QR fue fácil", 2),
    ("¿Tienen eventos este viernes? Quiero reservar una mesa", 1),
    ("Hola, ¿a qué hora abren y dónde queda?", 1),
    ("Muy buena noche, volveremos pronto", 0),
    ("Quiero cambiar la hora de llegada de mi reserva", 0),
    ("Hola, quiero saber qué eventos hay este fin de semana", 0),
]


def run() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = _usuario(db, "Admin Principal", "admin@medalloclub.com", "Administrador", "Admin123", "3000000000")
        carla = _usuario(db, "Carla Promotora", "promotora@medalloclub.com", "Promotor", "Promotor123", "3001112233")
        sebas = _usuario(db, "Sebastián Vélez", "sebastian@medalloclub.com", "Promotor", "Promotor123", "3004445566")
        vale = _usuario(db, "Valentina Ospina", "valentina@medalloclub.com", "Promotor", "Promotor123", "3007778899")
        _usuario(db, "Puerta Principal", "puerta@medalloclub.com", "Puerta", "Puerta123", "3002223344")
        _usuario(db, "Puerta Lateral", "puerta2@medalloclub.com", "Puerta", "Puerta123", "3003334455")

        # --- Noche pasada (cerrada): alimenta analítica, comisiones y riesgos ---------------------
        pasada, nueva = _evento(db, admin, "Noche Retro (cerrada)", -7, 150, "Éxitos de los 80 y 90", "cerrado", "evento-2-5c5c28983c17411dbebd8df76c242fbb.jpg")
        if nueva:
            for promotor, cantidad in ((carla, 18), (sebas, 14), (vale, 10)):
                lista = _invitados(db, pasada, promotor, [NOMBRES[(i * 3 + promotor.id) % len(NOMBRES)] + f" {i}" for i in range(cantidad)], usados=cantidad - 3)
                for inv in lista:
                    if inv.estado == "usado":
                        db.add(AccesoQRModel(invitado_id=inv.id, evento_id=pasada.id, tipo="qr", resultado="valido",
                                             fecha_hora=datetime.now(timezone.utc) - timedelta(days=7, hours=ALEATORIO.randint(0, 5))))
                valor = Decimal(cantidad - 3) * Decimal("20000") * Decimal("0.10")
                db.add(ComisionModel(promotor_id=promotor.id, evento_id=pasada.id, porcentaje=Decimal("10"), monto=valor,
                                     estado="liquidada", fecha_liquidacion=datetime.now(timezone.utc) - timedelta(days=5)))
            db.add(AccesoQRModel(evento_id=pasada.id, tipo="qr", resultado="duplicado", fecha_hora=datetime.now(timezone.utc) - timedelta(days=7)))
            db.add(AlertaRiesgoModel(evento_id=pasada.id, tipo_alerta="cortesia_duplicada", nivel="alto", estado="resuelta",
                                     descripcion="Intento de reingreso con un código QR ya utilizado (posible duplicación de cortesía)."))
            db.commit()

        # --- Próximos eventos con flyer --------------------------------------------------------
        viernes, nuevo_v = _evento(db, admin, "Noche Retro Viernes", 2, 150, "Éxitos de los 80 y 90", flyer="evento-2-5c5c28983c17411dbebd8df76c242fbb.jpg")
        _evento(db, admin, "Reggaeton Night", 9, 200, "Lo mejor del urbano latino", flyer="evento-9-f2d26c1e0c844d2ea94bc8f731fc10dd.jpg")
        _evento(db, admin, "Electro Sunset", 16, 120, "Música electrónica al atardecer", flyer="evento-3-bbdb5fe76e6646dea5b13d827c56fda9.png")

        if nuevo_v:
            _invitados(db, viernes, carla, NOMBRES[:6])
            _invitados(db, viernes, sebas, NOMBRES[6:10])
            db.add(ComisionModel(promotor_id=carla.id, evento_id=viernes.id, porcentaje=Decimal("10"), monto=Decimal("0"), estado="pendiente"))

            # Reservas: pendientes, garantizadas (con pases) y una cancelada.
            def reservar(nombre, tel, tipo, n, promotor=None):
                creada = reserva_service.crear_solicitud(
                    db, evento_id=viernes.id, nombre_cliente=nombre, telefono=tel, tipo=tipo, asistentes=n,
                    promotor_id=promotor.id if promotor else None,
                )
                return creada.reserva

            reservar("Camila Ríos", "+57 300 111 2233", "mesa", 4)
            reservar("Andrés Cardona", "+57 310 222 3344", "palco", 8, carla)
            g1 = reservar("Daniela Osorio", "+57 320 333 4455", "mesa", 6, sebas)
            g2 = reservar("Grupo Los Parceros", "+57 315 444 5566", "palco", 10)
            cancelada = reservar("Felipe Arias", "+57 301 555 6677", "mesa", 2)
            reserva_service.garantizar(db, g1, admin_id=admin.id, ubicacion_asignada="Mesa 12 · terraza", hora_limite="23:30", consumo_minimo=Decimal("600000"))
            reserva_service.garantizar(db, g2, admin_id=admin.id, ubicacion_asignada="Palco VIP 3", hora_limite="00:30", consumo_minimo=Decimal("1800000"))
            reserva_service.cancelar(db, cancelada, origen="solicitado por el cliente")

        # --- Inventario con historial y alertas -----------------------------------------------
        if not db.execute(select(InventarioItemModel)).first():
            catalogo = [
                ("Aguardiente Antioqueño", "Licores", 24, "botellas", 10, 78000, "Fábrica de Licores de Antioquia"),
                ("Ron Medellín", "Licores", 18, "botellas", 8, 95000, "Distribuidora Aburrá"),
                ("Whisky Etiqueta Negra", "Licores", 6, "botellas", 6, 180000, "Distribuidora Aburrá"),
                ("Vodka", "Licores", 3, "botellas", 6, 88000, "Distribuidora Aburrá"),
                ("Champaña", "Licores", 0, "botellas", 4, 210000, "Importadora Paisa"),
                ("Cerveza Club Colombia", "Cervezas", 120, "unidades", 48, 4200, "Bavaria"),
                ("Agua sin gas", "Bebidas", 90, "botellas", 36, 1800, "Postobón"),
                ("Gaseosas variadas", "Bebidas", 72, "unidades", 30, 2100, "Postobón"),
                ("Hielo", "Insumos", 14, "bolsas", 20, 5500, "Hielos del Valle"),
                ("Limones", "Insumos", 8, "kg", 5, 6000, "Plaza Minorista"),
                ("Vasos desechables", "Insumos", 400, "unidades", 200, 250, "Empaques SAS"),
                ("Servilletas", "Insumos", 35, "paquetes", 15, 3200, "Empaques SAS"),
            ]
            items = []
            for nombre, cat, cant, unidad, minimo, costo, proveedor in catalogo:
                item = InventarioItemModel(nombre=nombre, categoria=cat, cantidad=0, unidad=unidad, stock_minimo=minimo,
                                           costo_unitario=Decimal(costo), precio_venta=Decimal(round(costo * 2.2, -2)),
                                           proveedor=proveedor)
                db.add(item)
                db.flush()
                if cant > 0:
                    inventario_service.registrar_movimiento(db, item, tipo="entrada", cantidad=Decimal(cant) + Decimal(ALEATORIO.randint(5, 20)),
                                                            motivo="Compra inicial", usuario_id=admin.id)
                items.append((item, cant))
            db.commit()
            for item, objetivo in items:
                antes = inventario_service.estado_de(item)
                actual = Decimal(item.cantidad)
                if actual > Decimal(objetivo):
                    inventario_service.registrar_movimiento(db, item, tipo="consumo", cantidad=actual - Decimal(objetivo),
                                                            motivo="Consumo de la noche", evento_id=pasada.id, usuario_id=admin.id)
                    db.commit()
                inventario_service.evaluar_stock(db, item, antes if item.cantidad <= item.stock_minimo else inventario_service.EstadoStock(False, False))

        # --- Conversaciones del asistente (para el panel de sentimientos) ----------------------
        if not db.execute(select(ChatSesionModel)).first():
            for i, (texto, hace_dias) in enumerate(CONVERSACIONES):
                analisis = analizar_sentimiento(texto)
                momento = datetime.now(timezone.utc) - timedelta(days=hace_dias, hours=ALEATORIO.randint(0, 20))
                escalada = analisis["urgente"] or (analisis["etiqueta"] == "negativo" and analisis["intensidad"] == "alta")
                canal = "whatsapp" if i % 3 == 0 else "web"
                sesion = ChatSesionModel(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"medallo-demo-{i}")), canal=canal, contacto_hash=None,
                    estado_dialogo=json.dumps(estado_inicial()),
                    mensajes_total=1, negativos=1 if analisis["etiqueta"] == "negativo" else 0,
                    sentimiento_promedio=Decimal(str(analisis["puntaje"])), escalada=escalada,
                    escalada_resuelta=escalada and hace_dias >= 5, creada_en=momento, actualizada_en=momento,
                )
                db.add(sesion)
                db.flush()
                aspectos = ",".join(f"{a['aspecto']}:{a['sentimiento']}" for a in analisis["aspectos"])[:200] or None
                db.add(ChatMensajeModel(sesion_id=sesion.id, autor="usuario", texto=texto if canal == "web" else None,
                                        sentimiento=analisis["etiqueta"], puntaje=Decimal(str(analisis["puntaje"])),
                                        emocion=analisis["emocion"], aspectos=aspectos, intencion="queja_o_comentario", creado_en=momento))
            db.commit()

        print("Datos de demostración listos.")
        print("  Administrador: admin@medalloclub.com / Admin123")
        print("  Promotor:      promotora@medalloclub.com / Promotor123")
        print("  Puerta:        puerta@medalloclub.com / Puerta123")
    finally:
        db.close()


if __name__ == "__main__":
    run()
