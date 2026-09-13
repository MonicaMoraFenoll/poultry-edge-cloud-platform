# Poultry Edge-Cloud Platform

## Descripción

Este repositorio contiene la implementación de una plataforma **Edge-Cloud** para el conteo automático de huevos mediante visión por computador utilizando modelos YOLO.

La arquitectura separa las responsabilidades entre el procesamiento en los dispositivos **Edge** y los servicios centralizados utilizados para la gestión de modelos y datos:

- **Edge**: desplegado en cada granja, ejecuta la inferencia diaria, mantiene una copia local del modelo y gestiona la transferencia de los resultados.
- **MLflow Model Registry**: gestiona el versionado y la distribución de los modelos utilizados por los dispositivos Edge.
- **Azure Data Lake Storage Gen2 (ADLS Gen2)**: recibe los resultados generados en las granjas para su posterior procesamiento en la plataforma Cloud.

El diseño permite utilizar **el mismo código y la misma imagen Docker en todas las granjas**, modificando únicamente la configuración asignada a cada dispositivo.

---

## Estructura del repositorio

```text
.
├── data/
│   ├── outputs/
│   └── simulated/
│
├── edge/
│   ├── config/
│   ├── deployment/
│   ├── src/
│   │   └── poultry_edge/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
│
├── cloud/
|     |── lakehouse/
|     |── app/              
│
├── scripts/
│   ├── generate_mock_images.py
│   ├── generate_mock_egg_results.py
│   └── register_mock_model.py
│
└── README.md
```

### Responsabilidad de las carpetas

| Carpeta | Descripción |
|---|---|
| `data/` | Datos utilizados durante el desarrollo y resultados simulados. |
| `edge/config/` | Configuración específica de cada dispositivo/granja. |
| `edge/deployment/` | Scripts y unidades `systemd` utilizadas para aprovisionar y ejecutar el Edge. |
| `edge/src/poultry_edge/` | Código Python de inferencia, gestión de modelos e ingesta. |
| `edge/tests/` | Tests automatizados del componente Edge. |
| `cloud/` | Componentes de la plataforma Cloud. |
| `scripts/` | Scripts auxiliares para simulación y validación del prototipo. |

---

# 1. Datos simulados

## 1.1. Generación de imágenes simuladas

Para desarrollar y validar el pipeline sin depender inicialmente de las imágenes de una instalación real, el proyecto incorpora un script para generar una estructura de imágenes simulada.

Ejemplo:

```bash
python scripts/generate_mock_images.py \
    --houses 6 \
    --cages-per-house 20 \
    --start-date 2026-06-01 \
    --end-date 2026-06-30
```

La estructura generada sigue el patrón:

```text
data/simulated/
├── house_01/
│   └── 2026/
│       └── 06/
│           └── 30/
│               ├── cage_001.jpg
│               ├── cage_002.jpg
│               └── ...
└── ...
```

Cada imagen representa una captura asociada a una jaula y una fecha. Los ficheros simulados permiten reproducir la organización que tendría el almacenamiento local de un dispositivo Edge.

## 1.2. Generación de resultados de inferencia simulados

El script `generate_mock_egg_results.py` genera resultados de inferencia simulados para las tres granjas, respetando la estructura de naves y jaulas definida en los datos maestros.

Los datos incorporan:

- variabilidad productiva entre jaulas y días;
- una anomalía espacial persistente en una zona concreta de una batería;
- una caída productiva temporal;
- un pequeño porcentaje de errores técnicos de inferencia.

Estos escenarios permiten validar posteriormente las etapas de limpieza, contextualización, agregación y detección de anomalías del flujo de datos.

---

# 2. Componente Edge

Cada granja dispone conceptualmente de un dispositivo Edge independiente. Todos utilizan la misma aplicación y la misma imagen Docker; las diferencias entre instalaciones se definen mediante el fichero de configuración asignado al dispositivo.

```text
edge/
├── config/
├── deployment/
├── src/
│   └── poultry_edge/
├── tests/
├── Dockerfile
└── pyproject.toml
```

## 2.1. Configuración del Edge

Cada instalación dispone de un fichero YAML específico:

```text
edge/config/
├── farm_01.yml
├── farm_02.yml
└── farm_03.yml
```

Durante el aprovisionamiento, el fichero correspondiente a la granja se instala en el dispositivo como:

```text
/opt/poultry-edge/config/edge.yaml
```

El fichero define, entre otros:

- identificador de la granja;
- ubicación de las imágenes;
- directorio de resultados;
- modelo registrado en MLflow;
- alias del modelo asignado a la granja;
- directorio local de modelos;
- extensiones de imagen soportadas;
- ubicación de la base de datos local utilizada para mantener el estado de las transferencias.

Ejemplo de configuración del modelo:

```yaml
model:
  registered_name: egg_detector
  alias: farm_01_production
  local_root_directory: /app/models
```

De esta forma, la misma imagen Docker puede desplegarse en diferentes granjas cambiando únicamente la configuración instalada como `edge.yaml`.

---

# 3. Pipeline de inferencia

## 3.1. Módulos principales

El pipeline está implementado en:

```text
edge/src/poultry_edge/
```

| Módulo | Responsabilidad |
|---|---|
| `config.py` | Carga y validación del fichero YAML asignado al Edge. |
| `image_discovery.py` | Descubrimiento de las imágenes correspondientes a la fecha de procesamiento. |
| `model_loader.py` | Resolución de la versión activa en MLflow, sincronización local y fallback. |
| `inference.py` | Ejecución de la inferencia YOLO sobre las imágenes descubiertas. |
| `output_writer.py` | Escritura de los resultados de inferencia en CSV. |
| `pipeline.py` | Orquestación del pipeline diario. |
| `main.py` | Punto de entrada de la aplicación de inferencia. |

## 3.2. Flujo de ejecución

```text
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
Inferencia
        │
        ▼
Generación del CSV diario
```

La salida corresponde únicamente a la fecha procesada.

## 3.3. Resultados

Los resultados se almacenan en una estructura persistente:

```text
data/outputs/
└── YYYY/
    └── MM/
        └── DD/
            └── egg_prediction.csv
```

Cada fila representa una imagen procesada e incluye:

- `farm_id`;
- `house_number`;
- `cage_id`;
- fecha de captura y procesamiento;
- nombre y ruta de la imagen;
- tamaño del fichero;
- `egg_count`;
- confianza;
- nombre, versión y alias del modelo;
- fecha de sincronización del modelo;
- duración de la inferencia;
- estado de inferencia y mensaje de error.

---

# 4. Gestión y distribución de modelos con MLflow

## 4.1. Estrategia de registro

Los modelos se gestionan mediante **MLflow Model Registry**.

En lugar de mantener un modelo registrado diferente para cada granja, se utiliza un único modelo por tarea:

```text
egg_detector
```

Cada entrenamiento genera una nueva versión dentro del mismo modelo registrado.

Las versiones pueden incluir tags descriptivos, por ejemplo:

```text
farm_id = farm_01
task = egg_detection
model_type = YOLO
mock_model = true
```

Los **tags** proporcionan trazabilidad y contexto, mientras que los **aliases** determinan qué versión debe utilizar cada instalación.

Ejemplo:

```text
egg_detector
├── version 1 → farm_01_production
├── version 2 → farm_02_production
└── version 3 → farm_03_production
```

Cuando se registra una nueva versión para una granja, el alias correspondiente puede reasignarse:

```text
Antes:
farm_01_production → version 1

Después:
farm_01_production → version 4
```

La versión anterior permanece registrada en MLflow, manteniendo el histórico y permitiendo realizar un rollback si fuera necesario.

## 4.2. Registro de modelos de prueba

Para validar el mecanismo se utiliza `register_mock_model.py`.

Primero se inicia un servidor MLflow local:

```bash
mlflow server --host 127.0.0.1 --port 5000
```

En PowerShell puede configurarse:

```powershell
$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
```

Ejemplo de registro:

```bash
python scripts/register_mock_model.py \
    --model-path <path_to_model.pt> \
    --farm-id farm_01
```

El script:

1. registra el artefacto del modelo;
2. crea una nueva versión de `egg_detector`;
3. añade metadatos y tags;
4. asigna el alias `<farm_id>_production`.

## 4.3. Sincronización en el Edge

`model_loader.py` consulta en MLflow la versión asociada al alias configurado en `edge.yaml`.

Por ejemplo:

```text
registered_name = egg_detector
alias = farm_01_production
```

El Edge resuelve el alias, identifica la versión activa y la sincroniza con el almacenamiento local.

La estructura local sigue el patrón:

```text
models/
└── egg_detector/
    ├── versions/
    │   ├── 1/
    │   └── 4/
    └── current.json
```

`current.json` mantiene la referencia a la última versión sincronizada correctamente.

Si la versión resuelta ya está disponible localmente, se reutiliza sin necesidad de volver a descargarla. Si MLflow no está disponible temporalmente y existe una versión local válida, el pipeline puede utilizar la última versión sincronizada como **fallback**.

La sincronización puede validarse mediante `test_mlflow_sync.py`, que permite comprobar la resolución del alias, la versión obtenida y la ubicación de la copia local sincronizada.

---

# 5. Contenedorización

La aplicación Edge se distribuye mediante una imagen Docker común.

El `Dockerfile`:

- utiliza una imagen base NVIDIA/PyTorch;
- instala las dependencias del sistema;
- instala las dependencias Python;
- instala el paquete `poultry-edge`;
- contiene tanto la funcionalidad de inferencia como la de ingesta.

El paquete define dos entry points:

```text
poultry-edge
poultry-edge-upload
```

Por defecto, la imagen ejecuta:

```dockerfile
CMD ["poultry-edge"]
```

Por tanto, la misma imagen se utiliza para dos procesos independientes:

```text
MISMA IMAGEN DOCKER
        │
        ├── poultry-edge
        │       └── inferencia
        │
        └── poultry-edge-upload
                └── ingesta
```

No se mantienen imágenes Docker diferentes para ambos procesos.

---

# 6. CI/CD y despliegue del Edge

La estrategia de CI/CD utiliza **GitHub Actions, Docker y GitHub Container Registry (GHCR)**, separando la construcción del software, el aprovisionamiento inicial de los dispositivos y el despliegue de nuevas versiones.

Durante el prototipo, los tests, la construcción de la imagen y las simulaciones de aprovisionamiento y despliegue se ejecutaron mediante runners proporcionados por GitHub. En un entorno con dispositivos Edge físicos, el aprovisionamiento y despliegue requerirán *self-hosted runners* con acceso a los dispositivos o un mecanismo equivalente de despliegue remoto.

Se distinguen cuatro procesos:

1. construcción de la imagen Docker;
2. aprovisionamiento del dispositivo;
3. despliegue de una versión;
4. ejecución programada de los procesos Edge.

## 6.1. Workflows de GitHub Actions

Los workflows se encuentran en:

```text
.github/workflows/
├── build-edge-image.yml
├── edge-deploy.yml
├── edge-provisioning.yml
├── simulated-edge-deploy.yml
├── simulated-edge-provisioning.yml
└── test-edge.yml
```

| Workflow | Responsabilidad |
|---|---|
| `test-edge.yml` | Ejecutar automáticamente los tests del componente Edge y validar los cambios realizados en el código. |
| `build-edge-image.yml` | Ejecutar los tests y, únicamente si son satisfactorios, construir la imagen Docker y publicarla en GHCR. |
| `edge-provisioning.yml` | Preparar un nuevo dispositivo Edge físico e instalar su configuración, estructura persistente, scripts y unidades `systemd`. |
| `edge-deploy.yml` | Desplegar una versión concreta de la imagen Docker sobre un dispositivo Edge previamente aprovisionado. |
| `simulated-edge-provisioning.yml` | Reproducir el aprovisionamiento utilizando directorios locales que simulan diferentes dispositivos Edge. |
| `simulated-edge-deploy.yml` | Simular el despliegue de una versión sin disponer de dispositivos Edge físicos. |

## 6.2. Construcción de la imagen Docker

El workflow:

```text
.github/workflows/build-edge-image.yml
```

ejecuta los tests automatizados y, si finalizan correctamente, construye la imagen Docker y la publica en **GHCR** con las etiquetas definidas para su versionado.

La construcción se realiza en la infraestructura de GitHub Actions y no requiere utilizar los recursos de los dispositivos Edge.

## 6.3. Aprovisionamiento

El aprovisionamiento se realiza únicamente cuando se incorpora un nuevo dispositivo.

`install_edge.sh` recibe el fichero YAML correspondiente a la granja y prepara la estructura persistente:

```text
/opt/poultry-edge/
├── config/
│   └── edge.yaml
│
├── data/
│   ├── images/
│   ├── outputs/
│   ├── models/
│   └── state/
│
├── env/
│   └── poultry-edge.env
│
└── scripts/
    ├── run_edge.sh
    └── run_upload.sh
```

Además, instala las unidades `systemd` necesarias.

El código Python no se copia directamente al Edge: se distribuye dentro de la imagen Docker.

Para las simulaciones puede utilizarse un directorio de instalación alternativo. En este caso, el script crea la estructura local sin modificar el `systemd` real del equipo.

## 6.4. Despliegue de nuevas versiones

El workflow de despliegue permite seleccionar una versión concreta de la imagen Docker y desplegarla en un Edge previamente aprovisionado.

El proceso realiza:

- autenticación en GHCR;
- descarga (`pull`) de la imagen seleccionada;
- configuración del Edge para utilizar esa versión en las ejecuciones posteriores.

La configuración de la granja y los datos persistentes no se reemplazan durante el despliegue.

Esto permite desplegar una nueva versión inicialmente en una instalación concreta antes de extenderla al resto.

---

# 7. Ejecución automática de la inferencia

La ejecución diaria de la inferencia es independiente del despliegue del software.

Intervienen:

```text
poultry-edge.timer
poultry-edge.service
run_edge.sh
```

Flujo:

```text
poultry-edge.timer
        │
        ▼
poultry-edge.service
        │
        ▼
/opt/poultry-edge/scripts/run_edge.sh
        │
        ▼
docker run
        │
        ▼
poultry-edge
        │
        ▼
poultry_edge.main:main
        │
        ▼
Pipeline de inferencia
```

`run_edge.sh` monta en el contenedor:

- `edge.yaml`;
- imágenes;
- resultados;
- modelos locales.

El contenedor necesita acceso a GPU para ejecutar la inferencia.

Al utilizar `docker run --rm`, el contenedor es **efímero** y desaparece al terminar la ejecución. La configuración y los datos permanecen en el host mediante los directorios montados.

---

# 8. Ingesta de resultados hacia Azure

La ingesta se implementa como un proceso **independiente de la inferencia**, evitando que una interrupción de conectividad con Azure impida generar los resultados localmente.

Flujo general:

```text
Resultados locales
        │
        ▼
Descubrimiento
        │
        ▼
Registro persistente en SQLite
        │
        ▼
PENDING / FAILED
        │
        ▼
Transferencia a ADLS
        │
        ▼
Verificación
        │
        ├── correcta → UPLOADED
        │
        └── error    → FAILED
```

## 8.1. `upload_state.py`

Gestiona la base de datos SQLite utilizada para mantener el estado persistente de las transferencias.

Responsabilidades:

- inicializar la base de datos;
- registrar nuevos ficheros como `PENDING`;
- almacenar el número de intentos;
- registrar la fecha del último intento;
- marcar transferencias como `FAILED`;
- almacenar el último error;
- marcar transferencias como `UPLOADED`;
- recuperar registros `PENDING` y `FAILED`.

El estado se almacena fuera del contenedor en el directorio persistente `data/state/`.

## 8.2. `upload_discovery.py`

Descubre nuevos `egg_prediction.csv` generados por la inferencia.

Estructura local:

```text
/app/data/outputs/YYYY/MM/DD/egg_prediction.csv
```

Utiliza el `farm_id` definido en `edge.yaml` para construir la ruta remota:

```text
farm_id/YYYY/MM/DD/egg_prediction.csv
```

De esta forma, cada Edge envía únicamente los resultados correspondientes a su propia granja.

Los nuevos ficheros se registran en SQLite antes de intentar la transferencia.

## 8.3. `cloud_uploader.py`

Encapsula la comunicación con **Azure Data Lake Storage Gen2**.

Responsabilidades:

- crear el cliente ADLS;
- subir el fichero;
- consultar las propiedades del fichero remoto;
- verificar la transferencia comparando el tamaño local y remoto;
- generar un error cuando la verificación falla.

El fichero solo se considera transferido correctamente después de superar la verificación.

## 8.4. `upload_manager.py`

Gestiona el procesamiento y reintento de las transferencias.

Recupera los registros con estado:

```text
PENDING
FAILED
```

y procesa cada fichero de forma independiente.

```text
PENDING / FAILED ── éxito ──> UPLOADED
PENDING / FAILED ── error ──> FAILED
```

El fallo de un fichero no detiene el procesamiento de los demás.

## 8.5. `upload_results.py`

Es el punto de entrada del proceso de ingesta.

Responsabilidades:

1. cargar `edge.yaml`;
2. obtener `farm_id`, `outputs` y `state_database`;
3. inicializar SQLite;
4. descubrir nuevos resultados;
5. crear el cliente ADLS;
6. procesar los registros `PENDING` y `FAILED`;
7. registrar el resumen de la ejecución.

El paquete expone este proceso mediante:

```text
poultry-edge-upload
```

En el prototipo, el nombre de la cuenta de almacenamiento y el filesystem `landing` se mantienen definidos estáticamente en este módulo.

## 8.6. `run_upload.sh`

Ejecuta la ingesta dentro de la misma imagen Docker utilizada para la inferencia, sobrescribiendo el comando por defecto:

```text
docker run ... IMAGE poultry-edge-upload
```

Monta únicamente los recursos necesarios:

```text
config  → lectura
outputs → lectura
state   → lectura/escritura
```

La ingesta no requiere GPU.

## 8.7. Automatización con `systemd`

Intervienen:

```text
poultry-edge-upload.timer
poultry-edge-upload.service
run_upload.sh
```

Flujo:

```text
poultry-edge-upload.timer
        │
        ▼
poultry-edge-upload.service
        │
        ▼
run_upload.sh
        │
        ▼
docker run
        │
        ▼
poultry-edge-upload
        │
        ▼
upload_results.py
        │
        ├── upload_discovery.py
        ├── upload_state.py
        ├── upload_manager.py
        └── cloud_uploader.py
        │
        ▼
Azure Data Lake Storage Gen2
        │
        ▼
Landing
```

Inferencia e ingesta crean **contenedores efímeros independientes a partir de la misma imagen Docker**. Esto permite reintentar las transferencias sin volver a ejecutar la inferencia.

## 8.8. Validación del estado persistente

El mecanismo de persistencia puede validarse mediante el script de prueba correspondiente (scripts/demo_upload_state.py), que reproduce de forma controlada la transición:

```text
PENDING → FAILED → UPLOADED
```

La prueba permite comprobar la actualización persistente del estado, el número de intentos, el último error y las marcas temporales asociadas a la transferencia.

---

# 9. Tests y calidad del código

Los tests automatizados del componente Edge se encuentran en:

```text
edge/tests/
```

Pueden ejecutarse mediante:

```bash
pytest
```

Para comprobar la cobertura:

```bash
pytest --cov=poultry_edge --cov-report=term-missing
```

Los tests cubren las principales responsabilidades del Edge, incluyendo:

- configuración;
- descubrimiento de imágenes;
- inferencia;
- sincronización y fallback de modelos;
- generación de resultados;
- descubrimiento y estado persistente de transferencias;
- gestión y orquestación de la ingesta.

En la validación actual, la batería de tests alcanza una **cobertura global de código del 93 %**.

La validación automatizada se integra en GitHub Actions para detectar errores ante cambios en el código y evitar la construcción de una nueva imagen cuando los tests no finalizan correctamente.

---

# 10. Flujo completo del Edge

```text
                         MLflow Model Registry
                                 │
                    egg_detector + farm alias
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                            EDGE                             │
│                                                             │
│  Images                                                     │
│    │                                                        │
│    ▼                                                        │
│  poultry-edge.timer                                         │
│    │                                                        │
│    ▼                                                        │
│  run_edge.sh → Docker → poultry-edge                        │
│                         │                                   │
│                         ├── sincronización del modelo        │
│                         ├── inferencia                       │
│                         └── egg_prediction.csv               │
│                                      │                      │
│                                      ▼                      │
│                               data/outputs                  │
│                                      │                      │
│                                      ▼                      │
│                        poultry-edge-upload.timer             │
│                                      │                      │
│                                      ▼                      │
│                        run_upload.sh → Docker                │
│                                      │                      │
│                                      ▼                      │
│                           poultry-edge-upload                │
│                                      │                      │
│                          SQLite state + reintentos           │
└──────────────────────────────────────┼──────────────────────┘
                                       │
                                       ▼
                          Azure Data Lake Storage
                                       │
                                       ▼
                                    Landing
```

La arquitectura mantiene separados el ciclo de inferencia, la distribución de modelos y la transferencia de resultados, conservando localmente los elementos necesarios para tolerar interrupciones temporales de conectividad.

---

# 11. Cloud

El procesamiento Cloud se implementó mediante **Azure Data Lake Storage (ADLS)** 
y **Azure Databricks**, siguiendo una arquitectura Medallion:

**Landing → Bronze → Silver → Gold → Detección de anomalías**

Los notebooks desarrollados se encuentran en:

```text
cloud/
└── lakehouse/
    ├── 01_bronze_ingestion
    ├── 02_silver_processing
    ├── 03_gold_analytics
    └── 04_anomaly_detection

## 11.1 Landing

Los ficheros `egg_prediction.csv` enviados desde los dispositivos Edge se almacenan inicialmente en la zona **Landing** de ADLS, organizados por granja y fecha:

```text
landing/<farm_id>/<YYYY>/<MM>/<DD>/egg_prediction.csv
```

## 11.2 Bronze

El notebook `01_bronze_ingestion` realiza la ingesta de los ficheros almacenados en Landing:

- Lee los ficheros CSV.
- Añade información de trazabilidad.
- Almacena los datos en formato **Delta Lake**.

Salida:

```text
lakehouse/bronze/egg_predictions
```

## 11.3 Silver

El notebook `02_silver_processing` valida y enriquece los resultados de inferencia utilizando los datos maestros almacenados en **Azure Database for PostgreSQL**.

Databricks se conecta a PostgreSQL mediante **JDBC** y relaciona los resultados de inferencia con los datos maestros utilizando:

```text
farm_id + house_number + cage_id
```
Salida:

```text
lakehouse/silver/egg_predictions
```

## 11.4 Gold

El notebook `03_gold_analytics` genera conjuntos de datos preparados para su explotación analítica.

### Daily production

`daily_production` agrega los resultados por granja, nave, batería y día, generando métricas de producción y calidad.

Salida:

```text
lakehouse/gold/daily_production
```

### Spatial monitoring

`spatial_monitoring` agrega los resultados por batería, nivel, lado y grupos de posiciones, permitiendo analizar patrones espaciales dentro de cada batería.

Salida:

```text
lakehouse/gold/spatial_monitoring
```

## 11.5 Detección de anomalías

El notebook `04_anomaly_detection` utiliza los conjuntos de datos Gold para identificar automáticamente dos tipos de anomalías:

- **Anomalías temporales:** desviaciones de producción respecto al comportamiento histórico de cada batería.
- **Anomalías espaciales:** zonas con un comportamiento anómalo persistente respecto al resto de la batería.

El resultado se almacena en:

```text
lakehouse/gold/detected_anomalies
```

## 11.6 Orquestación

Los cuatro notebooks se integraron en un **Databricks Workflow**, estableciendo las dependencias necesarias entre las distintas etapas:

```text
01_bronze_ingestion
        ↓
02_silver_processing
        ↓
03_gold_analytics
        ↓
04_anomaly_detection
```

El workflow completo se ejecutó satisfactoriamente, validando la automatización del pipeline Cloud desde la ingesta de los datos hasta la generación de los conjuntos analíticos y la detección de anomalías.

12. Aplicación de Streamlit

Debido a los créditos de subscripción de Azure Student no se se pudo realizar la visualización en la plataforma Cloud, pero creamos la aplicación en local cloud/app/app.py. Para ello, en scripts se generaron los datos de entrada para la aplicación (generate_data_streamlit.py). Este apartado tiene su propio README.md donde explica como levantar la aplicación. 