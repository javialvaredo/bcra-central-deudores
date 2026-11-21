# BCRA – Central de Deudores

Cliente en Python e interfaz web local para consultar la API pública **Central de Deudores v1.0** del Banco Central de la República Argentina (BCRA).

- Documentación oficial: https://www.bcra.gob.ar/documentacion-apis/?fileName=central-deudores-v1
- Aviso legal: https://www.bcra.gob.ar/aviso-legal/

## Qué hace

Permite consultar, por CUIT / CUIL / CDI (11 dígitos):

| Consulta | Endpoint | Contenido |
|---|---|---|
| `deudas` | `GET /CentralDeDeudores/v1.0/Deudas/{id}` | Situación crediticia del último período informado |
| `historicas` | `GET /CentralDeDeudores/v1.0/Deudas/Historicas/{id}` | Situación de los últimos 24 meses |
| `cheques` | `GET /CentralDeDeudores/v1.0/Deudas/ChequesRechazados/{id}` | Cheques rechazados y sus causales |

Base URL: `https://api.bcra.gob.ar`. No requiere autenticación.

## Estructura

```
BCRA_central_deudores/
├── bcra_central_deudores.py   # Cliente de la API + línea de comandos
├── app_web.py                 # Servidor Flask local
├── templates/
│   └── index.html             # Interfaz web (formulario de CUIT)
├── requirements.txt
└── README.md
```

## Instalación

Requiere Python 3.9 o superior.

### 1. Crear y activar el entorno virtual

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
Si PowerShell bloquea scripts: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
En CMD: `.venv\Scripts\activate.bat`.

Ubuntu / Linux:
```bash
sudo apt install python3-venv   # si hace falta
python3 -m venv .venv
source .venv/bin/activate
```

> No copies la carpeta `.venv` entre Windows y Ubuntu: no es portable. Creá un entorno en cada sistema.

### 2. Instalar dependencias

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Uso

### Interfaz web

```bash
python app_web.py
```

Abrí http://127.0.0.1:5000, ingresá el CUIT, elegí el tipo de consulta y presioná **Consultar**.

El servidor escucha solo en `127.0.0.1`. No lo expongas en una red pública (ver [Privacidad](#privacidad-y-aviso-legal)).

### Línea de comandos

```bash
python bcra_central_deudores.py deudas 20123456786
python bcra_central_deudores.py historicas 20123456786 --csv historico.csv
python bcra_central_deudores.py cheques 20123456786 --json
```

Opciones:

| Opción | Descripción |
|---|---|
| `--json` | Imprime la respuesta cruda en JSON |
| `--csv ARCHIVO` | Exporta a CSV (una fila por período y entidad, o por cheque) |
| `--no-verify-ssl` | Desactiva la verificación SSL (solo si falla el certificado; no recomendado) |

Códigos de salida: `0` ok, `1` error, `2` sin datos (404).

### Como librería

```python
from bcra_central_deudores import CentralDeudores, SinDatos

api = CentralDeudores()
try:
    informe = api.deudas("20123456786")
except SinDatos:
    print("Sin datos para ese CUIT")
```

Métodos: `deudas()`, `historicas()`, `cheques_rechazados()`.
Excepciones: `BCRAError` (base), `IdentificacionInvalida` (400), `SinDatos` (404).

## Interpretación de los datos

**Situación del deudor** (clasificación informada por la entidad):

| Código | Cartera comercial | Cartera consumo / vivienda |
|---|---|---|
| 1 | En situación normal | Situación normal |
| 2 | Con seguimiento especial | Riesgo bajo |
| 3 | Con problemas | Riesgo medio |
| 4 | Con alto riesgo de insolvencia | Riesgo alto |
| 5 | Irrecuperable | Irrecuperable |

- `monto` en **deudas** e **históricas**: miles de pesos.
- `monto` en **cheques rechazados**: pesos.
- `diasAtrasoPago = 0` significa "No aplicable".
- `enRevision` y `procesoJud` indican información sometida a revisión (Ley 25.326, art. 16 inc. 6) o a proceso judicial (art. 38 inc. 3).

## Manejo de errores

| Status | Significado | Comportamiento |
|---|---|---|
| 400 | Identificación inválida (no son 11 dígitos) | `IdentificacionInvalida` |
| 404 | Sin datos para la identificación | `SinDatos` |
| 429 / 5xx | Control de tráfico o error del servidor | Reintenta 3 veces con espera creciente |

El BCRA aplica control de tráfico por dirección IP. Evitá ráfagas de consultas.

## Notas sobre la documentación del BCRA

Los ejemplos de error de `Históricas` y `Cheques Rechazados` en el manual (v1.0) usan la ruta `CentralDeInformacion`, pero los requests documentados usan `CentralDeDeudores`. Este proyecto usa `CentralDeDeudores`.

## Privacidad y aviso legal

- Los datos consultados son datos personales regidos por la **Ley 25.326**. Usalos únicamente con base legal para consultarlos.
- Los derechos de rectificación, actualización, supresión y confidencialidad se ejercen ante la entidad informante, no ante este proyecto ni ante el BCRA.
- Según el Aviso legal del BCRA:
  - Citar la fuente: *Banco Central de la República Argentina (BCRA)*.
  - No alterar el significado ni el contexto de la información.
  - No usar con fines comerciales, publicitarios o de campaña sin autorización previa y expresa del BCRA.
  - El BCRA no garantiza la disponibilidad de la API y puede modificarla o discontinuarla sin aviso.
  - La difusión de los datos no implica conformidad del BCRA.
- Este proyecto no guarda consultas ni datos en disco, salvo el CSV que pidas explícitamente.

## Solución de problemas

**`ModuleNotFoundError: No module named 'requests'`**
El entorno no tiene las dependencias. Con el entorno activo: `python -m pip install -r requirements.txt`. Verificá con `where python` (Windows) o `which python` (Linux) que apunte a `.venv`.

**`TemplateNotFound: index.html`**
La carpeta debe llamarse `templates` y estar junto a `app_web.py`.

**Error de certificado SSL**
Actualizá `certifi` (`python -m pip install -U certifi requests`). Usá `--no-verify-ssl` solo como último recurso.

**404 "No se encontró datos"**
El CUIT no tiene deudas ni cheques informados, o no existe.

**Puerto 5000 ocupado**
Cambiá `port=5000` en `app_web.py`.

## Licencia y fuente de datos

El código de este proyecto es de uso libre del autor. Los datos pertenecen al BCRA y están sujetos a su [Aviso legal](https://www.bcra.gob.ar/aviso-legal/).
