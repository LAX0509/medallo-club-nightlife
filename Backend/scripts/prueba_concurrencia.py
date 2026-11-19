"""Prueba de concurrencia y carga contra un backend en ejecución (idealmente con PostgreSQL).

Verifica la propiedad más importante del control de acceso: un mismo QR escaneado al mismo
tiempo en varias puertas debe producir EXACTAMENTE un ingreso válido (el resto, duplicados),
y mide latencias con carga mixta.

Uso (con el backend corriendo y datos demo cargados):
    python -m scripts.prueba_concurrencia --base http://127.0.0.1:8000 \
        --email admin@medalloclub.com --password Admin123
"""

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx


def _login(cliente: httpx.Client, base: str, email: str, password: str) -> dict[str, str]:
    r = cliente.post(f"{base}/api/v1/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def run(base: str, email: str, password: str, hilos: int, intentos: int, carga: int) -> dict:
    with httpx.Client(timeout=30) as cliente:
        auth = _login(cliente, base, email, password)
        evento = cliente.post(
            f"{base}/api/v1/eventos",
            json={"nombre": f"Prueba de concurrencia {int(time.time())}", "fecha": (date.today() + timedelta(days=30)).isoformat(), "aforo_maximo": 10000},
            headers=auth,
        ).json()
        promotores = cliente.get(f"{base}/api/v1/usuarios?rol=Promotor", headers=auth).json()["items"]
        promotor_id = promotores[0]["id"]

        def crear_pase(i: int) -> str:
            r = cliente.post(
                f"{base}/api/v1/invitados",
                json={"nombre": f"Invitado carga {i}", "evento_id": evento["id"], "promotor_id": promotor_id},
                headers=auth,
            )
            r.raise_for_status()
            return r.json()["qr_code"]

        # 1) Carrera por un mismo QR desde varias "puertas" a la vez.
        resultados_carrera = []
        for ronda in range(intentos):
            codigo = crear_pase(10_000 + ronda)

            def escanear(_):
                with httpx.Client(timeout=30) as c:
                    r = c.post(f"{base}/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": codigo}, headers=auth)
                    return r.json()["acceso"]["resultado"] if r.status_code == 201 else f"HTTP {r.status_code}"

            with ThreadPoolExecutor(max_workers=hilos) as pool:
                resultados = list(pool.map(escanear, range(hilos)))
            resultados_carrera.append({"validos": resultados.count("valido"), "duplicados": resultados.count("duplicado"), "otros": [x for x in resultados if x not in ("valido", "duplicado")]})

        # 2) Carga mixta: pases distintos escaneados en paralelo; mide latencia y errores.
        codigos = [crear_pase(i) for i in range(carga)]
        latencias: list[float] = []

        def escanear_unico(codigo: str) -> str:
            with httpx.Client(timeout=30) as c:
                inicio = time.perf_counter()
                r = c.post(f"{base}/api/v1/accesos", json={"evento_id": evento["id"], "qr_code": codigo}, headers=auth)
                latencias.append((time.perf_counter() - inicio) * 1000)
                return r.json()["acceso"]["resultado"] if r.status_code == 201 else f"HTTP {r.status_code}"

        inicio_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=hilos) as pool:
            resultados_carga = list(pool.map(escanear_unico, codigos))
        duracion = time.perf_counter() - inicio_total
        latencias.sort()

        # Limpieza: el evento de prueba se elimina (cascada sobre invitados y accesos).
        cliente.delete(f"{base}/api/v1/eventos/{evento['id']}", headers=auth)

    carrera_ok = all(r["validos"] == 1 and not r["otros"] for r in resultados_carrera)
    return {
        "hilos": hilos,
        "carrera_mismo_qr": {"rondas": intentos, "aprobada": carrera_ok, "detalle": resultados_carrera},
        "carga_mixta": {
            "solicitudes": len(codigos),
            "validos": resultados_carga.count("valido"),
            "errores": [r for r in resultados_carga if r != "valido"],
            "solicitudes_por_segundo": round(len(codigos) / duracion, 1),
            "latencia_ms": {
                "p50": round(statistics.median(latencias), 1),
                "p95": round(latencias[int(len(latencias) * 0.95) - 1], 1),
                "max": round(latencias[-1], 1),
            },
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default="admin@medalloclub.com")
    parser.add_argument("--password", default="Admin123")
    parser.add_argument("--hilos", type=int, default=12)
    parser.add_argument("--rondas", type=int, default=8)
    parser.add_argument("--carga", type=int, default=150)
    args = parser.parse_args()
    informe = run(args.base, args.email, args.password, args.hilos, args.rondas, args.carga)
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    sys.exit(0 if informe["carrera_mismo_qr"]["aprobada"] and not informe["carga_mixta"]["errores"] else 1)
