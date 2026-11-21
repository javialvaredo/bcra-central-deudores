#!/usr/bin/env python3
"""
Cliente para la API pública "Central de Deudores" v1.0 del BCRA.

Fuente: Banco Central de la República Argentina (BCRA).
Documentación: https://www.bcra.gob.ar/documentacion-apis/?fileName=central-deudores-v1

Endpoints (base: https://api.bcra.gob.ar/CentralDeDeudores/v1.0):
    GET /Deudas/{identificacion}                    -> último período informado
    GET /Deudas/Historicas/{identificacion}         -> últimos 24 meses
    GET /Deudas/ChequesRechazados/{identificacion}  -> cheques rechazados

Notas importantes (Aviso legal del BCRA, https://www.bcra.gob.ar/aviso-legal/):
  * Citar la fuente ("Banco Central de la República Argentina" / "BCRA").
  * No alterar el significado ni el contexto de la información.
  * No usar con fines comerciales, publicitarios o de campaña sin autorización
    previa y expresa del BCRA.
  * El BCRA no garantiza disponibilidad ininterrumpida de la API y puede
    modificarla o discontinuarla sin aviso.
  * El tratamiento de datos personales se rige por la Ley 25.326.
  * La difusión de los datos no implica conformidad del BCRA.

Autenticación: no requerida. El tráfico se controla por IP, por lo que se
recomienda no abusar de la API (este script reintenta con espera creciente).

Uso como librería:
    from bcra_central_deudores import CentralDeudores
    api = CentralDeudores()
    informe = api.deudas("20123456786")

Uso por línea de comandos:
    python bcra_central_deudores.py deudas 20123456786
    python bcra_central_deudores.py historicas 20123456786 --csv historico.csv
    python bcra_central_deudores.py cheques 20123456786 --json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from typing import Any

import requests

BASE_URL = "https://api.bcra.gob.ar/CentralDeDeudores/v1.0"

SITUACIONES = {
    1: "Situación normal",
    2: "Con seguimiento especial / Riesgo bajo",
    3: "Con problemas / Riesgo medio",
    4: "Con alto riesgo de insolvencia / Riesgo alto",
    5: "Irrecuperable",
}


# --------------------------------------------------------------------------
# Excepciones
# --------------------------------------------------------------------------
class BCRAError(Exception):
    """Error genérico de la API del BCRA."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class IdentificacionInvalida(BCRAError):
    """CUIT/CUIL/CDI con formato inválido (400 o validación local)."""


class SinDatos(BCRAError):
    """No se encontraron datos para la identificación (404)."""


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------
def validar_identificacion(identificacion: str | int) -> str:
    """Devuelve la identificación como string de 11 dígitos o lanza error."""
    ident = str(identificacion).strip().replace("-", "")
    if not (ident.isdigit() and len(ident) == 11):
        raise IdentificacionInvalida(
            "La identificación debe tener 11 dígitos (CUIT/CUIL/CDI).", status=400
        )
    return ident


def cuit_digito_valido(ident: str) -> bool:
    """Verifica el dígito verificador del CUIT/CUIL (módulo 11). Informativo."""
    pesos = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(d) * p for d, p in zip(ident[:10], pesos))
    dv = 11 - (suma % 11)
    dv = {11: 0, 10: 9}.get(dv, dv)
    return dv == int(ident[10])


# --------------------------------------------------------------------------
# Cliente
# --------------------------------------------------------------------------
class CentralDeudores:
    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 20.0,
        reintentos: int = 3,
        espera: float = 1.5,
        verify_ssl: bool = True,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.reintentos = reintentos
        self.espera = espera
        self.session = requests.Session()
        self.session.verify = verify_ssl
        self.session.headers.update({"Accept": "application/json"})

    # -- núcleo ----------------------------------------------------------
    def _get(self, ruta: str) -> dict[str, Any]:
        url = f"{self.base_url}/{ruta}"
        ultimo_error: Exception | None = None

        for intento in range(1, self.reintentos + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:  # red, timeout, SSL
                ultimo_error = BCRAError(f"Error de conexión: {exc}")
            else:
                # La API devuelve el status también en el cuerpo JSON.
                try:
                    cuerpo = resp.json()
                except ValueError:
                    cuerpo = {}
                status = cuerpo.get("status", resp.status_code)
                mensajes = "; ".join(cuerpo.get("errorMessages", [])) or resp.reason

                if status == 200 and resp.ok:
                    return cuerpo
                if status == 400:
                    raise IdentificacionInvalida(mensajes, status=400)
                if status == 404:
                    raise SinDatos(mensajes, status=404)
                if status in (429, 500, 502, 503, 504) or resp.status_code in (
                    429, 500, 502, 503, 504,
                ):
                    ultimo_error = BCRAError(mensajes, status=status)
                else:
                    raise BCRAError(f"Respuesta inesperada ({status}): {mensajes}", status)

            if intento < self.reintentos:
                time.sleep(self.espera * (2 ** (intento - 1)))

        raise ultimo_error or BCRAError("Error desconocido")

    # -- endpoints -------------------------------------------------------
    def deudas(self, identificacion: str | int) -> dict[str, Any]:
        """Situación crediticia del último período informado."""
        ident = validar_identificacion(identificacion)
        return self._get(f"Deudas/{ident}")["results"]

    def historicas(self, identificacion: str | int) -> dict[str, Any]:
        """Situación crediticia de los últimos 24 meses."""
        ident = validar_identificacion(identificacion)
        return self._get(f"Deudas/Historicas/{ident}")["results"]

    def cheques_rechazados(self, identificacion: str | int) -> dict[str, Any]:
        """Cheques rechazados con sus causales."""
        ident = validar_identificacion(identificacion)
        return self._get(f"Deudas/ChequesRechazados/{ident}")["results"]


# --------------------------------------------------------------------------
# Aplanado de resultados (para CSV / tablas)
# --------------------------------------------------------------------------
def aplanar_periodos(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Una fila por (período, entidad). Sirve para /Deudas y /Historicas."""
    filas = []
    for p in results.get("periodos", []):
        for e in p.get("entidades", []):
            fila = {
                "identificacion": results.get("identificacion"),
                "denominacion": results.get("denominacion"),
                "periodo": p.get("periodo"),
            }
            fila.update(e)
            filas.append(fila)
    return filas


def aplanar_cheques(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Una fila por cheque rechazado."""
    filas = []
    for c in results.get("causales", []):
        for e in c.get("entidades", []):
            for d in e.get("detalle", []):
                fila = {
                    "identificacion": results.get("identificacion"),
                    "denominacion": results.get("denominacion"),
                    "causal": c.get("causal"),
                    "entidad": e.get("entidad"),
                }
                fila.update(d)
                filas.append(fila)
    return filas


def guardar_csv(filas: list[dict[str, Any]], ruta: str) -> None:
    if not filas:
        print("No hay filas para exportar.", file=sys.stderr)
        return
    columnas: list[str] = []
    for f in filas:
        for k in f:
            if k not in columnas:
                columnas.append(k)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=columnas)
        w.writeheader()
        w.writerows(filas)
    print(f"CSV guardado en {ruta} ({len(filas)} filas)")


# --------------------------------------------------------------------------
# Presentación en consola
# --------------------------------------------------------------------------
def imprimir_periodos(results: dict[str, Any]) -> None:
    print(f"Identificación: {results.get('identificacion')}")
    print(f"Denominación:   {results.get('denominacion')}")
    for p in results.get("periodos", []):
        print(f"\nPeríodo {p['periodo']}")
        for e in p.get("entidades", []):
            sit = e.get("situacion")
            print(
                f"  - {e.get('entidad')}: situación {sit} "
                f"({SITUACIONES.get(sit, '?')}), monto ${e.get('monto')} miles"
                + (f", atraso {e['diasAtrasoPago']} días" if e.get("diasAtrasoPago") else "")
                + (" [EN REVISIÓN]" if e.get("enRevision") else "")
                + (" [PROCESO JUDICIAL]" if e.get("procesoJud") else "")
            )
    print("\nMontos en miles de pesos. Fuente: Banco Central de la República Argentina (BCRA).")


def imprimir_cheques(results: dict[str, Any]) -> None:
    print(f"Identificación: {results.get('identificacion')}")
    print(f"Denominación:   {results.get('denominacion')}")
    filas = aplanar_cheques(results)
    if not filas:
        print("Sin cheques rechazados.")
    for f in filas:
        print(
            f"  - Cheque {f.get('nroCheque')} | {f.get('causal')} | entidad {f.get('entidad')} | "
            f"rechazo {f.get('fechaRechazo')} | ${f.get('monto')} | "
            f"pago {f.get('fechaPago')} | multa: {f.get('fechaPagoMulta') or f.get('estadoMulta')}"
        )
    print("\nFuente: Banco Central de la República Argentina (BCRA).")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Consulta a la Central de Deudores del BCRA (API v1.0)")
    ap.add_argument("consulta", choices=["deudas", "historicas", "cheques"])
    ap.add_argument("identificacion", help="CUIT/CUIL/CDI (11 dígitos)")
    ap.add_argument("--json", action="store_true", help="Imprimir JSON crudo")
    ap.add_argument("--csv", metavar="ARCHIVO", help="Exportar a CSV")
    ap.add_argument("--no-verify-ssl", action="store_true",
                    help="Desactiva la verificación SSL (solo si falla el certificado; no recomendado)")
    args = ap.parse_args(argv)

    api = CentralDeudores(verify_ssl=not args.no_verify_ssl)

    try:
        ident = validar_identificacion(args.identificacion)
        if not cuit_digito_valido(ident):
            print("Aviso: el dígito verificador no coincide; se consulta igual.", file=sys.stderr)

        if args.consulta == "deudas":
            res, aplanar, mostrar = api.deudas(ident), aplanar_periodos, imprimir_periodos
        elif args.consulta == "historicas":
            res, aplanar, mostrar = api.historicas(ident), aplanar_periodos, imprimir_periodos
        else:
            res, aplanar, mostrar = api.cheques_rechazados(ident), aplanar_cheques, imprimir_cheques
    except SinDatos as e:
        print(f"Sin datos: {e}", file=sys.stderr)
        return 2
    except BCRAError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        mostrar(res)
    if args.csv:
        guardar_csv(aplanar(res), args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
