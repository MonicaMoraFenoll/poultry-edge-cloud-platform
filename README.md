# Poultry Edge-Cloud Platform

## Descripción

Este repositorio contiene la implementación de una plataforma **Edge-Cloud** para el conteo automático de huevos mediante visión por computador utilizando modelos YOLO.

La plataforma se divide en dos componentes independientes:

- **Edge**, desplegado en cada granja, encargado de ejecutar la inferencia diaria sobre las imágenes capturadas.
- **Cloud**, encargado del entrenamiento, versionado y distribución de modelos mediante MLflow.

Ambos componentes comparten el mismo repositorio para facilitar el desarrollo, el despliegue y el mantenimiento del sistema.

---

# Estructura del repositorio

```
.
├── data/
│   ├── outputs/
│   └── simulated/
│
├── poultry_edge/
│   ├── config/
│   ├── deployment/
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── cloud/
│
├── scripts/
│   └── generate_mock_images.py
│
└── README.md
```

## Descripción de las carpetas

| Carpeta | Descripción |
|----------|-------------|
| **data/** | Datos utilizados durante el desarrollo y resultados generados por el pipeline Edge. |
| **edge/** | Código fuente del dispositivo Edge encargado de ejecutar la inferencia. |
| **cloud/** | Código relacionado con el entrenamiento, registro y gestión de modelos. |
| **scripts/** | Scripts auxiliares utilizados durante el desarrollo del proyecto. |

---

# Generación del conjunto de datos simulado

Para facilitar el desarrollo sin necesidad de disponer de imágenes reales, el proyecto incorpora un script que genera un conjunto de imágenes simuladas con la misma estructura de directorios utilizada por el Edge.

La estructura generada es la siguiente:

```
data/simulated/
├── house_01/
│   └── 2026/
│       └── 06/
│           └── 30/
│               ├── cage_001.jpg
│               ├── cage_002.jpg
│               └── ...
├── house_02/
│   └── 2026/
│       └── 06/
│           └── 30/
└── ...
```

Cada imagen representa una captura correspondiente a una jaula determinada en una fecha concreta.

Actualmente los archivos `.jpg` generados son archivos vacíos cuyo único propósito es simular la organización del almacenamiento de imágenes que existiría en un dispositivo Edge real.

---

# Generar el conjunto de datos

Ejemplo de ejecución:

```bash
python scripts/generate_mock_images.py \
    --houses 6 \
    --cages-per-house 20 \
    --start-date 2026-06-01 \
    --end-date 2026-06-30
```

El comando anterior genera:

- 6 naves.
- 20 jaulas por nave.
- 30 días de imágenes.

En total:

```
6 × 20 × 30 = 3.600 imágenes simuladas
```

---

# Componente Edge

Cada granja dispone de un dispositivo Edge independiente encargado de ejecutar diariamente el pipeline de inferencia.

El Edge está organizado como un paquete Python independiente.

```
edge/
├── config/
├── deployment/
├── src/
│   └── poultry_edge/
├── tests/
├── Dockerfile
└── pyproject.toml
```

## Configuración

Cada dispositivo utiliza un único fichero YAML de configuración.

```
edge/config/
├── farm_01.yml
├── farm_02.yml
└── farm_03.yml
```

Cada fichero define:

- identificador de la granja;
- ubicación de las imágenes;
- directorio de salida;
- modelo asignado;
- alias del modelo;
- extensiones soportadas.

De esta forma, la misma imagen Docker puede desplegarse en diferentes granjas utilizando únicamente un fichero de configuración distinto.

---

## Arquitectura del pipeline Edge

El pipeline se encuentra implementado en:

```
edge/src/poultry_edge/
```

Los módulos principales son:

| Módulo | Función |
|---------|---------|
| `config.py` | Carga y validación de la configuración del Edge. |
| `image_discovery.py` | Descubrimiento de las imágenes correspondientes a la fecha de procesamiento. |
| `model_loader.py` | Sincronización del modelo desde MLflow y carga del modelo YOLO. |
| `inference.py` | Ejecución de la inferencia sobre todas las imágenes descubiertas. |
| `output_writer.py` | Escritura de los resultados diarios en formato CSV. |
| `pipeline.py` | Orquestación del pipeline completo. |
| `main.py` | Punto de entrada de la aplicación. |

---

## Flujo de ejecución

Cada ejecución del Edge sigue el siguiente flujo:

```
Carga de configuración
          │
          ▼
Sincronización del modelo
          │
          ▼
Carga del modelo YOLO
          │
          ▼
Descubrimiento de imágenes
          │
          ▼
Inferencia sobre todas las imágenes
          │
          ▼
Generación del CSV diario
```

La salida generada corresponde únicamente a la fecha procesada.

---

## Resultados

Los resultados se almacenan automáticamente en:

```
data/outputs/

└── YYYY/
    └── MM/
        └── DD/
            └── egg_predictions.csv
```

Cada fila del CSV representa una imagen procesada e incluye, entre otros, los siguientes campos:

- identificador de la granja;
- identificador de la nave;
- identificador de la jaula;
- fecha de captura;
- número de huevos detectados;
- confianza media de las detecciones;
- modelo utilizado;
- versión del modelo;
- tiempo de inferencia;
- estado de la inferencia.

---

## Arquitectura CI/CD

El sistema Edge utiliza una arquitectura de Integración y Despliegue Continuo (CI/CD) basada en GitHub Actions, Docker y runners autoalojados (self-hosted runners).

La arquitectura se divide en cuatro fases independientes:

Construcción de la imagen Docker (CI).
Aprovisionamiento del dispositivo Edge.
Despliegue de nuevas versiones.
Ejecución diaria de la inferencia.

Cada fase tiene una única responsabilidad, facilitando el mantenimiento, la actualización y la escalabilidad del sistema.

1. Construcción de la imagen Docker

Workflow:

.github/workflows/build-edge-image.yml

Responsabilidad:

Construir la imagen Docker de la aplicación.
Instalar todas las dependencias Python.
Generar e instalar el paquete Python del proyecto.
Publicar la imagen Docker en GitHub Container Registry (GHCR).

La imagen Docker contiene:

el código fuente completo de la aplicación;
todas las dependencias necesarias;
el pipeline de inferencia;
el punto de entrada de la aplicación.

Durante esta fase no interviene ningún dispositivo Edge, ya que toda la construcción se realiza utilizando los recursos del runner de GitHub Actions.

2. Aprovisionamiento del Edge

Workflow:

.github/workflows/edge-provisioning.yml

El aprovisionamiento únicamente se realiza cuando se incorpora un nuevo dispositivo Edge al sistema.

Su responsabilidad consiste en preparar el dispositivo para que posteriormente pueda recibir y ejecutar la aplicación.

Tras el aprovisionamiento, el Edge dispone de la siguiente estructura persistente:

/opt/poultry-edge/
├── config/
│   └── edge.yaml
├── data/
│   ├── images/
│   ├── models/
│   └── outputs/
└── scripts/
    └── run_edge.sh

Durante este proceso se realizan las siguientes acciones:

instalación del fichero de configuración correspondiente a la granja;
creación de los directorios persistentes;
instalación del script de ejecución (run_edge.sh);
instalación y habilitación del servicio y temporizador de systemd.

El código fuente de la aplicación no se copia al Edge, ya que se distribuye exclusivamente mediante imágenes Docker.

3. Despliegue de nuevas versiones

Workflow:

.github/workflows/edge-deploy.yml

Responsabilidad:

Desplegar una versión concreta de la imagen Docker en una granja seleccionada.

El workflow se ejecuta sobre el runner correspondiente al Edge seleccionado y realiza las siguientes operaciones:

autenticación en GitHub Container Registry;
descarga de la imagen Docker correspondiente a la versión seleccionada;
configuración del Edge para utilizar dicha versión en las siguientes ejecuciones.

Este mecanismo permite realizar despliegues controlados, validando nuevas versiones sobre una única granja antes de extenderlas al resto del sistema.

4. Ejecución diaria de la inferencia

La ejecución de la inferencia es completamente independiente del proceso de despliegue.

La planificación queda gestionada por Linux mediante:

run_edge.sh
poultry-edge.service
poultry-edge.timer

El flujo de ejecución es el siguiente:

11:00
    │
    ▼
poultry-edge.timer
    │
    ▼
poultry-edge.service
    │
    ▼
run_edge.sh
    │
    ▼
docker run
    │
    ▼
poultry_edge.main
    │
    ▼
Pipeline de inferencia
    │
    ▼
Resultados CSV

El script run_edge.sh crea un contenedor Docker utilizando la imagen previamente desplegada y monta los directorios persistentes necesarios para la ejecución:

configuración del Edge;
imágenes de entrada;
modelos almacenados localmente;
directorio de resultados.

Una vez finalizada la inferencia, el contenedor Docker se elimina automáticamente, mientras que la imagen Docker permanece almacenada en el dispositivo. De este modo, únicamente será necesario descargar una nueva imagen cuando se despliegue una nueva versión de la aplicación.

## Ingesta de resultados hacia Azure

## Ingesta de resultados hacia Azure

La ingesta de los resultados generados en el Edge se implementa como un proceso independiente de la inferencia. Su objetivo es detectar nuevos ficheros de resultados, registrar su estado localmente, transferirlos a Azure Data Lake Storage Gen2 y reintentar automáticamente aquellos envíos que hayan fallado.

El flujo general es:

```text
Resultados locales
      ↓
Descubrimiento de ficheros
      ↓
Registro en SQLite
      ↓
PENDING / FAILED
      ↓
Transferencia a ADLS
      ↓
Verificación del fichero
      ↓
UPLOADED / FAILED

upload_state.py

Gestiona la base de datos SQLite utilizada para mantener el estado persistente de las transferencias.

Responsabilidades principales:

crear la base de datos de estado;
registrar nuevos ficheros como PENDING;
marcar una transferencia como FAILED cuando se produce un error;
marcar una transferencia como UPLOADED cuando finaliza correctamente;
almacenar el número de intentos, el último error y las fechas de transferencia;
recuperar los ficheros PENDING y FAILED para reintentarlos.

La base de datos se almacena en un directorio persistente del dispositivo Edge, de forma que el estado de las transferencias se conserva aunque el contenedor Docker sea sustituido o actualizado.

upload_discovery.py

Busca automáticamente los nuevos ficheros egg_prediction.csv generados por el Edge.

La estructura local esperada es:

/app/data/outputs/YYYY/MM/DD/egg_prediction.csv

A partir del farm_id definido en el archivo de configuración del dispositivo, construye la ruta de destino en Azure:

farm_id/YYYY/MM/DD/egg_prediction.csv

Los nuevos ficheros encontrados se registran en la base de datos SQLite como pendientes de transferencia.

cloud_uploader.py

Implementa la comunicación con Azure Data Lake Storage Gen2.

Sus principales responsabilidades son:

crear el cliente de conexión con ADLS;
transferir un fichero local a la ruta remota correspondiente;
verificar la transferencia comparando el tamaño del fichero local y remoto;
generar un error cuando la transferencia no puede considerarse válida.

El fichero se considera correctamente transferido únicamente después de superar esta verificación.

upload_manager.py

Coordina el procesamiento de los ficheros pendientes.

Obtiene de SQLite todos los registros con estado PENDING o FAILED e intenta transferirlos individualmente mediante cloud_uploader.py.

Si una transferencia finaliza correctamente:

PENDING / FAILED → UPLOADED

Si se produce un error:

PENDING / FAILED → FAILED

El fallo de un fichero no detiene el procesamiento de los restantes, permitiendo continuar con el resto del lote.

upload_results.py

Actúa como punto de entrada del proceso de ingesta.

Sus responsabilidades son:

cargar la configuración del dispositivo Edge;
obtener el farm_id, el directorio local de resultados y la ubicación de la base SQLite;
inicializar la base de datos de estado;
descubrir nuevos resultados;
crear el cliente de Azure Data Lake Storage;
procesar los ficheros pendientes y fallidos;
registrar un resumen de la ejecución.

En producción, este módulo se ejecuta mediante el comando:

poultry-edge-upload

definido como entry point del paquete Python.

run_upload.sh

Script de despliegue encargado de ejecutar el proceso de ingesta dentro de la imagen Docker del componente Edge.

Monta únicamente los recursos necesarios:

configuración → lectura
outputs       → lectura
state         → lectura/escritura

y ejecuta:

poultry-edge-upload

La inferencia y la ingesta utilizan la misma imagen Docker, pero se ejecutan como procesos independientes.

poultry-edge-upload.service

Servicio systemd encargado de ejecutar run_upload.sh.

Permite desacoplar la ingesta del proceso de inferencia y consultar su estado y logs de forma independiente.

poultry-edge-upload.timer

Temporizador systemd encargado de ejecutar periódicamente el servicio de ingesta.

Gracias al estado persistente almacenado en SQLite, cada ejecución puede recuperar transferencias anteriores que no se completaron correctamente, permitiendo tolerar interrupciones temporales de conectividad.

El flujo de ejecución completo es:

poultry-edge-upload.timer
        ↓
poultry-edge-upload.service
        ↓
run_upload.sh
        ↓
Docker
        ↓
poultry-edge-upload
        ↓
upload_results.py
        ↓
upload_discovery.py
        ↓
upload_state.py
        ↓
upload_manager.py
        ↓
cloud_uploader.py
        ↓
Azure Data Lake Storage Gen2




#####################


Para levantar el mlflow local: mlflow server --host 127.0.0.1 --port 5000
$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"

se han hecho los tests: pytest --cov=poultry_edge --cov-report=term-missing -> github actions de forma automatica si han cambio en el codigo




El script generate_mock_egg_results.py genera resultados de inferencia simulados durante cinco días para las tres granjas, respetando la estructura de naves y jaulas definida en los datos maestros.
Los datos incorporan variabilidad productiva entre jaulas y días, una anomalía espacial persistente en una zona concreta de una batería, una caída productiva temporal y un pequeño porcentaje de errores técnicos de inferencia. Estos escenarios permiten validar posteriormente las etapas de limpieza, contextualización, agregación y detección de anomalías del flujo de datos.

Uploaded state: nuevo CSV
   ↓
PENDING
   ↓
fallo Azure
   ↓
FAILED
   ↓
siguiente ejecución
   ↓
se vuelve a intentar
   ↓
UPLOADED

# Próximos pasos

Las siguientes fases del proyecto consistirán en:

1. Simular la llegada diaria de nuevas imágenes al dispositivo Edge.
2. Implementar un pipeline de inferencia simulado que genere el número de huevos detectados por jaula.
3. Desarrollar la aplicación Edge encargada del procesamiento automático.
4. Sincronizar los resultados con una plataforma Cloud.
5. Desarrollar un dashboard para la visualización y análisis de los fenotipos digitales obtenidos.