from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_dashboard_service, get_db, require_roles
from app.application import bot_config, informe_service
from app.application.dashboard_service import DashboardService
from app.application.ia_client import ClienteIA
from app.core.config import get_settings
from app.domain.enums import RolUsuario
from app.schemas.alerta_riesgo_schema import AlertaRiesgoRespuesta
from app.schemas.dashboard_schema import ResumenEventoRespuesta

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard gerencial"],
    dependencies=[Depends(require_roles(RolUsuario.ADMINISTRADOR))],
)


@router.get("/eventos/{evento_id}/resumen", response_model=ResumenEventoRespuesta)
def resumen_evento(
    evento_id: int, dashboard_service: DashboardService = Depends(get_dashboard_service)
) -> ResumenEventoRespuesta:
    resumen = dashboard_service.generar_resumen(evento_id)
    return ResumenEventoRespuesta(
        evento_id=resumen.evento_id,
        evento_nombre=resumen.evento_nombre,
        aforo_maximo=resumen.aforo_maximo,
        accesos_validos=resumen.accesos_validos,
        accesos_duplicados=resumen.accesos_duplicados,
        accesos_rechazados=resumen.accesos_rechazados,
        porcentaje_aforo=resumen.porcentaje_aforo,
        comisiones_pendientes=resumen.comisiones_pendientes,
        comisiones_liquidadas=resumen.comisiones_liquidadas,
        alertas_activas=[
            AlertaRiesgoRespuesta.model_validate(a) for a in resumen.alertas_activas
        ],
        nivel_riesgo_general=resumen.nivel_riesgo_general,
        recomendacion=resumen.recomendacion,
    )


class InformeEntrada(BaseModel):
    usar_ia: bool = True


@router.post("/eventos/{evento_id}/informe")
def informe_de_jornada(
    evento_id: int, payload: InformeEntrada | None = None, db: Session = Depends(get_db)
) -> dict:
    """Informe de cierre con cifras reales, lectura gerencial y recomendaciones (IA o reglas)."""
    payload = payload or InformeEntrada()
    informe = informe_service.construir_informe(db, evento_id)
    config = bot_config.obtener_config(db)
    ia = ClienteIA(
        get_settings(),
        habilitada=bot_config.es_verdadero(config, "ia_habilitada"),
        limite_diario=int(config["ia_limite_diario"]),
    )
    narrativa = informe_service.generar_narrativa(db, informe, usar_ia=payload.usar_ia, ia=ia)
    informe.pop("recomendaciones_reglas", None)
    return {**informe, "narrativa": narrativa}
