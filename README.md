# Poultry Edge-Cloud Platform

## Descripción

Este repositorio contiene la implementación de una plataforma **Edge-Cloud** para la generación, gestión y explotación de fenotipos digitales obtenidos mediante visión por computador.

El conteo automático de huevos se utiliza como caso de estudio para validar una arquitectura distribuida en la que el procesamiento se realiza localmente en dispositivos Edge y los resultados se integran posteriormente en una plataforma Cloud para su almacenamiento, contextualización y explotación analítica.

La arquitectura separa las principales responsabilidades del sistema:

- **Edge**: ejecuta la inferencia, mantiene una copia local del modelo y gestiona la transferencia de los resultados.
- **MLflow Model Registry**: gestiona el versionado y la distribución de los modelos utilizados por los dispositivos Edge.
- **Azure Data Lake Storage Gen2 (ADLS Gen2)**: recibe y almacena los resultados generados en las granjas.
- **Azure Databricks**: implementa el procesamiento Cloud mediante una arquitectura Medallion.
- **Azure Database for PostgreSQL**: centraliza los datos maestros utilizados para contextualizar los fenotipos.
- **Streamlit**: permite la visualización y explotación de los resultados generados.

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
│   ├── lakehouse/
│   └── app/
│
├── database/
│   ├── schema.sql
│   ├── sample_master_data.sql
│   └── README.md
│
├── scripts/
│   ├── generate_mock_images.py
│   ├── generate_mock_egg_results.py
│   ├── generate_data_streamlit.py
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
| `edge/src/poultry_edge/` | Código Python de inferencia, gestión de modelos y transferencia de resultados. |
| `edge/tests/` | Tests automatizados del componente Edge. |
| `cloud/lakehouse/` | Notebooks utilizados para implementar el procesamiento Cloud. |
| `cloud/app/` | Aplicación Streamlit para la explotación de los resultados. |
| `database/` | Esquema relacional y datos maestros utilizados por la plataforma. Incluye un README específico con la descripción del modelo y las instrucciones de despliegue. |
| `scripts/` | Scripts auxiliares para simulación y validación del prototipo. |

---

# 1. Datos simulados

## 1.1. Generación de imágenes simuladas

Para desarrollar y validar el pipeline Edge sin depender inicialmente de imágenes procedentes de una instalación real, el proyecto incorpora un script para generar una estructura de imágenes simulada.

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

Cada imagen representa una captura asociada a una jaula y una fecha. Estos ficheros permiten reproducir la organización esperada del almacenamiento local de un dispositivo Edge.

## 1.2. Generación de resultados de inferencia simulados

El script `generate_mock_egg_results.py` genera directamente resultados de inferencia simulados para las tres granjas, respetando la estructura de naves y jaulas definida en los datos maestros.

Los datos incorporan:

- variabilidad productiva entre jaulas y días;
- una anomalía espacial persistente en una zona concreta de una batería;
- una caída productiva temporal;
- un pequeño porcentaje de errores técnicos de inferencia.

Estos resultados constituyen el conjunto utilizado para validar el procesamiento Cloud y permiten comprobar las etapas de contextualización, agregación y detección de anomalías sin necesidad de ejecutar el modelo de visión artificial sobre todas las observaciones simuladas.

---

# 2. Componente Edge

Cada granja dispone conceptualmente de un dispositivo Edge independiente. Todos utilizan la misma aplicación y la misma imagen Docker; las diferencias entre instalaciones se definen mediante la configuración asignada al dispositivo.

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

El repositorio contiene un fichero YAML específico para cada instalación:

```text
edge/config/
├── farm_01.yml
├── farm_02.yml
└── farm_03.yml
```

Durante el aprovisionamiento, el fichero correspondiente se copia en el dispositivo como un único fichero de configuración local:

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

Ejemplo:

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
| `config.py` | Carga y validación de la configuración asignada al Edge. |
| `image_discovery.py` | Descubrimiento de las imágenes correspondientes a la fecha de procesamiento. |
| `model_loader.py` | Resolución de la versión activa en MLflow, sincronización local y fallback. |
| `inference.py` | Ejecución de la inferencia sobre las imágenes descubiertas. |
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
Carga del modelo
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

Cada fila representa una imagen procesada e incluye información sobre:

- granja, nave y jaula;
- fecha de captura y procesamiento;
- imagen procesada;
- resultado y confianza de la inferencia;
- modelo, versión y alias utilizados;
- fecha de sincronización del modelo;
- duración de la inferencia;
- estado de la inferencia y posibles errores.

---

# 4. Gestión y distribución de modelos con MLflow

## 4.1. Estrategia de registro

Los modelos se gestionan mediante **MLflow Model Registry**.

En lugar de mantener un modelo registrado diferente para cada granja, se utiliza un único modelo por tarea:

```text
egg_detector
```

Cada entrenamiento genera una nueva versión dentro del mismo modelo registrado.

Los **tags** proporcionan trazabilidad y contexto, mientras que los **aliases** determinan qué versión debe utilizar cada instalación.

Ejemplo:

```text
egg_detector
├── version 1 → farm_01_production
├── version 2 → farm_02_production
└── version 3 → farm_03_production
```

Cuando se registra una nueva versión, el alias correspondiente puede reasignarse:

```text
Antes:
farm_01_production → version 1

Después:
farm_01_production → version 4
```

La versión anterior permanece registrada en MLflow, manteniendo el histórico y permitiendo realizar un rollback si fuera necesario.

## 4.2. Registro de modelos de prueba

Para validar el mecanismo se utiliza:

```text
scripts/register_mock_model.py
```

Durante el prototipo se utilizó un servidor MLflow local:

```bash
mlflow server --host 127.0.0.1 --port 5000
```

El script registra el artefacto, crea una nueva versión del modelo, añade la información asociada y asigna el alias correspondiente.

## 4.3. Sincronización en el Edge

`model_loader.py` consulta en MLflow la versión asociada al alias configurado en `edge.yaml`.

El Edge resuelve el alias, identifica la versión activa y la sincroniza con el almacenamiento local:

```text
models/
└── egg_detector/
    ├── versions/
    │   ├── 1/
    │   └── 4/
    └── current.json
```

`current.json` mantiene la referencia a la última versión sincronizada correctamente.

Si la versión ya está disponible localmente, se reutiliza. Si MLflow no está disponible temporalmente y existe una versión local válida, el pipeline utiliza la última versión sincronizada como **fallback**.

---

# 5. Contenedorización

La aplicación Edge se distribuye mediante una imagen Docker común.

El `Dockerfile`:

- utiliza una imagen base NVIDIA/PyTorch;
- instala las dependencias necesarias;
- instala el paquete `poultry-edge`;
- contiene tanto la funcionalidad de inferencia como la de transferencia de resultados.

El paquete define dos entry points:

```text
poultry-edge
poultry-edge-upload
```

Por tanto, la misma imagen se utiliza para dos procesos independientes:

```text
MISMA IMAGEN DOCKER
        │
        ├── poultry-edge
        │       └── inferencia
        │
        └── poultry-edge-upload
                └── transferencia de resultados
```

No se mantienen imágenes Docker diferentes para ambos procesos.

---

# 6. CI/CD y despliegue del Edge

La estrategia de CI/CD utiliza **GitHub Actions, Docker y GitHub Container Registry (GHCR)**, separando la construcción del software, el aprovisionamiento inicial y el despliegue de nuevas versiones.

Durante el prototipo, los tests, la construcción de la imagen y las simulaciones de aprovisionamiento y despliegue se ejecutaron mediante runners proporcionados por GitHub. En un entorno con dispositivos Edge físicos, el aprovisionamiento y despliegue requerirán *self-hosted runners* con acceso a los dispositivos o un mecanismo equivalente de despliegue remoto.

Se distinguen cuatro procesos:

1. construcción de la imagen Docker;
2. aprovisionamiento del dispositivo;
3. despliegue de una versión;
4. ejecución programada de los procesos Edge.

## 6.1. Workflows de GitHub Actions

```text
.github/workflows/
├── build-edge-image.yml
├── edge-deploy.yml
├── edge-provisioning.yml
├── simulated-edge-deploy.yml
└── simulated-edge-provisioning.yml
```

| Workflow | Responsabilidad |
|---|---|
| `build-edge-image.yml` | Ejecutar los tests y, únicamente si son satisfactorios, construir la imagen Docker y publicarla en GHCR. |
| `edge-provisioning.yml` | Preparar un dispositivo Edge físico e instalar su configuración, estructura persistente, scripts y unidades `systemd`. |
| `edge-deploy.yml` | Desplegar una versión concreta de la imagen Docker sobre un Edge previamente aprovisionado. |
| `simulated-edge-provisioning.yml` | Reproducir el aprovisionamiento utilizando directorios locales. |
| `simulated-edge-deploy.yml` | Simular el despliegue de una versión sin disponer de dispositivos Edge físicos. |

## 6.2. Construcción de la imagen Docker

`build-edge-image.yml` ejecuta los tests automatizados y, si finalizan correctamente, construye la imagen Docker y la publica en **GHCR** con las etiquetas definidas para su versionado.

La construcción se realiza mediante GitHub Actions y no requiere utilizar recursos del dispositivo Edge.

## 6.3. Aprovisionamiento

El aprovisionamiento se realiza únicamente al incorporar un nuevo dispositivo.

`install_edge.sh` prepara la estructura persistente:

```text
/opt/poultry-edge/
├── config/
│   └── edge.yaml
├── data/
│   ├── images/
│   ├── outputs/
│   ├── models/
│   └── state/
├── env/
│   └── poultry-edge.env
└── scripts/
    ├── run_edge.sh
    └── run_upload.sh
```

Además, instala las unidades `systemd` necesarias.

El código Python no se copia directamente al Edge, sino que se distribuye dentro de la imagen Docker.

## 6.4. Despliegue de nuevas versiones

El workflow de despliegue permite seleccionar una versión de la imagen Docker y desplegarla en un Edge previamente aprovisionado.

El proceso realiza:

- autenticación en GHCR;
- descarga (`pull`) de la imagen seleccionada;
- configuración del Edge para utilizar esa versión.

La configuración de la granja y los datos persistentes no se reemplazan durante el despliegue.

---

# 7. Ejecución automática de la inferencia

La ejecución de la inferencia es independiente del despliegue del software.

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
run_edge.sh
        │
        ▼
docker run
        │
        ▼
poultry-edge
        │
        ▼
Pipeline de inferencia
```

`run_edge.sh` monta en el contenedor la configuración, las imágenes, los resultados y los modelos locales.

El contenedor dispone de acceso a GPU para ejecutar la inferencia.

Al utilizar `docker run --rm`, el contenedor es **efímero** y desaparece al finalizar la ejecución. La configuración y los datos permanecen en el host mediante directorios persistentes.

---

# 8. Transferencia de resultados hacia Azure

La transferencia se implementa como un proceso **independiente de la inferencia**, evitando que una interrupción de conectividad con Azure impida generar resultados localmente.

La comunicación con **Azure Data Lake Storage Gen2** se realiza mediante el **SDK de Azure para Python**.

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

## 8.1. Estado persistente de las transferencias

`upload_state.py` gestiona una base de datos SQLite utilizada para mantener el estado de cada fichero.

Los estados principales son:

```text
PENDING
FAILED
UPLOADED
```

La base de datos registra también el número de intentos, el último error y las marcas temporales asociadas.

El estado se almacena fuera del contenedor en:

```text
data/state/
```

## 8.2. Descubrimiento de resultados

`upload_discovery.py` identifica nuevos `egg_prediction.csv` y utiliza el `farm_id` definido en `edge.yaml` para construir la ruta remota:

```text
farm_id/YYYY/MM/DD/egg_prediction.csv
```

Los nuevos ficheros se registran en SQLite antes de intentar su transferencia.

## 8.3. Transferencia a ADLS

`cloud_uploader.py` encapsula la comunicación con **Azure Data Lake Storage Gen2 mediante el SDK de Azure para Python**.

El módulo:

- crea el cliente ADLS;
- transfiere el fichero;
- consulta las propiedades del fichero remoto;
- verifica la transferencia comparando el tamaño local y remoto.

El fichero únicamente se marca como `UPLOADED` después de superar esta verificación.

## 8.4. Gestión y reintentos

`upload_manager.py` procesa los registros `PENDING` y `FAILED` de forma independiente:

```text
PENDING / FAILED ── éxito ──> UPLOADED
PENDING / FAILED ── error ──> FAILED
```

El fallo de un fichero no detiene el procesamiento de los demás.

## 8.5. Ejecución y automatización

El proceso se expone mediante:

```text
poultry-edge-upload
```

y se ejecuta utilizando la misma imagen Docker que la inferencia:

```text
docker run ... IMAGE poultry-edge-upload
```

La ejecución automática se gestiona mediante:

```text
poultry-edge-upload.timer
poultry-edge-upload.service
run_upload.sh
```

Inferencia y transferencia crean **contenedores efímeros independientes a partir de la misma imagen Docker**, permitiendo reintentar las transferencias sin volver a ejecutar la inferencia.

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

Los tests cubren las principales responsabilidades del Edge:

- configuración;
- descubrimiento de imágenes;
- inferencia;
- sincronización y fallback de modelos;
- generación de resultados;
- descubrimiento y estado persistente de transferencias;
- gestión de la transferencia hacia Cloud.

La validación automatizada se integra en GitHub Actions para detectar errores ante cambios en el código y evitar la construcción de una nueva imagen cuando los tests no finalizan correctamente.

---

# 10. Datos maestros

Los datos maestros utilizados para contextualizar los resultados de inferencia se gestionan mediante **Azure Database for PostgreSQL**.

El esquema y los scripts asociados se encuentran en:

```text
database/
├── schema.sql
├── sample_master_data.sql
└── README.md
```

El modelo representa la jerarquía física:

```text
Granja → Nave → Batería → Jaula
```

incluyendo el nivel, lado y posición de cada jaula.

La integración con los resultados de inferencia se realiza mediante:

```text
farm_id + house_number + cage_id
```

El directorio `database/` dispone de un **README específico** donde se describe con mayor detalle el modelo relacional, las tablas, relaciones y restricciones, así como las instrucciones necesarias para crear y cargar la base de datos.

---

# 11. Procesamiento Cloud

El procesamiento Cloud se implementó mediante **Azure Data Lake Storage Gen2** y **Azure Databricks**, siguiendo una arquitectura Medallion.

El flujo general es:

```text
Landing
   ↓
Bronze
   ↓
Silver
   ↓
Gold
   ↓
Detección de anomalías
   ↓
Explotación de resultados
```

Los notebooks desarrollados se encuentran en:

```text
cloud/
└── lakehouse/
    ├── 01_bronze_ingestion
    ├── 02_silver_processing
    ├── 03_gold_analytics
    └── 04_anomaly_detection
```

## 11.1. Landing

Los `egg_prediction.csv` enviados desde los dispositivos Edge se almacenan inicialmente en ADLS:

```text
landing/<farm_id>/<YYYY>/<MM>/<DD>/egg_prediction.csv
```

## 11.2. Bronze

`01_bronze_ingestion`:

- lee los CSV almacenados en Landing;
- añade información de trazabilidad;
- almacena los datos en formato **Delta Lake**.

Salida:

```text
lakehouse/bronze/egg_predictions
```

## 11.3. Silver

`02_silver_processing` valida y enriquece los resultados utilizando los datos maestros almacenados en **Azure Database for PostgreSQL**.

Databricks se conecta a PostgreSQL mediante **JDBC** y relaciona ambas fuentes mediante:

```text
farm_id + house_number + cage_id
```

Salida:

```text
lakehouse/silver/egg_predictions
```

## 11.4. Gold

`03_gold_analytics` genera los conjuntos preparados para la explotación analítica.

### Daily production

`daily_production` agrega los resultados por granja, nave, batería y día.

```text
lakehouse/gold/daily_production
```

### Spatial monitoring

`spatial_monitoring` agrega los resultados por batería, nivel, lado y grupos de posiciones para analizar patrones espaciales.

```text
lakehouse/gold/spatial_monitoring
```

## 11.5. Detección de anomalías

`04_anomaly_detection` utiliza los conjuntos Gold para identificar automáticamente:

- **anomalías temporales**: desviaciones respecto al comportamiento histórico de cada batería;
- **anomalías espaciales**: zonas con un comportamiento anómalo persistente respecto al resto de la batería.

Los resultados se almacenan en:

```text
lakehouse/gold/detected_anomalies
```

## 11.6. Orquestación

Los cuatro notebooks se integraron en un **Databricks Workflow**:

```text
01_bronze_ingestion
        ↓
02_silver_processing
        ↓
03_gold_analytics
        ↓
04_anomaly_detection
```

La ejecución completa del workflow permitió validar la automatización del pipeline Cloud desde la ingesta hasta la generación de los conjuntos analíticos y la detección de anomalías.

---

# 12. Aplicación de visualización

Los conjuntos generados en la capa Gold se explotan mediante una aplicación desarrollada con **Streamlit**, ubicada en:

```text
cloud/app/app.py
```

Debido al agotamiento de los créditos disponibles en la suscripción **Azure for Students**, la aplicación se ejecutó y validó localmente.

Para reproducir los resultados obtenidos previamente durante el procesamiento Cloud, se utiliza:

```text
scripts/generate_data_streamlit.py
```

que genera los conjuntos de datos de entrada necesarios para la aplicación.

La interfaz permite:

- consultar los principales indicadores productivos;
- analizar su evolución temporal;
- analizar patrones espaciales;
- consultar las anomalías detectadas por el pipeline.

El directorio:

```text
cloud/app/
```

incluye un **README específico** con las instrucciones necesarias para ejecutar la aplicación.