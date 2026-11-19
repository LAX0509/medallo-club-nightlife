from fastapi import APIRouter

from app.api.v1.accesos_router import router as accesos_router
from app.api.v1.alertas_router import router as alertas_router
from app.api.v1.auth_router import router as auth_router
from app.api.v1.bot_router import router as bot_router
from app.api.v1.chat_router import router as chat_router
from app.api.v1.comisiones_router import router as comisiones_router
from app.api.v1.dashboard_router import router as dashboard_router
from app.api.v1.eventos_router import router as eventos_router
from app.api.v1.invitados_router import router as invitados_router
from app.api.v1.inventario_router import router as inventario_router
from app.api.v1.reservas_router import router as reservas_router
from app.api.v1.sentimientos_router import router as sentimientos_router
from app.api.v1.notificaciones_router import router as notificaciones_router
from app.api.v1.pases_router import router as pases_router
from app.api.v1.promotores_router import router as promotores_router
from app.api.v1.usuarios_router import router as usuarios_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(usuarios_router)
api_router.include_router(eventos_router)
api_router.include_router(accesos_router)
api_router.include_router(invitados_router)
api_router.include_router(inventario_router)
api_router.include_router(comisiones_router)
api_router.include_router(alertas_router)
api_router.include_router(dashboard_router)
api_router.include_router(reservas_router)
api_router.include_router(sentimientos_router)
api_router.include_router(promotores_router)
api_router.include_router(notificaciones_router)
api_router.include_router(pases_router)
api_router.include_router(chat_router)
api_router.include_router(bot_router)
