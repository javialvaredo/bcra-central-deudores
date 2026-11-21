#!/usr/bin/env python3
"""Interfaz web local para la Central de Deudores del BCRA.

Ejecutar:  python app_web.py   y abrir  http://127.0.0.1:5000
Requiere:  pip install flask requests

Se escucha solo en 127.0.0.1 (tu PC): los datos consultados son personales
(Ley 25.326), por lo que no conviene exponer esta app en una red pública.
Fuente de los datos: Banco Central de la República Argentina (BCRA).
"""
from flask import Flask, jsonify, render_template, request

from bcra_central_deudores import (
    BCRAError,
    CentralDeudores,
    IdentificacionInvalida,
    SinDatos,
    cuit_digito_valido,
    validar_identificacion,
)

app = Flask(__name__)
api = CentralDeudores()


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/consulta")
def consulta():
    body = request.get_json(silent=True) or {}
    tipo = body.get("tipo", "deudas")
    try:
        ident = validar_identificacion(body.get("cuit", ""))
        if tipo == "deudas":
            data = api.deudas(ident)
        elif tipo == "historicas":
            data = api.historicas(ident)
        elif tipo == "cheques":
            data = api.cheques_rechazados(ident)
        else:
            return jsonify(ok=False, error="Tipo de consulta inválido."), 400
    except IdentificacionInvalida as e:
        return jsonify(ok=False, error=str(e)), 400
    except SinDatos as e:
        return jsonify(ok=False, error=str(e)), 404
    except BCRAError as e:
        return jsonify(ok=False, error=f"Error al consultar el BCRA: {e}"), 502

    return jsonify(ok=True, tipo=tipo, data=data, dv_valido=cuit_digito_valido(ident))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)