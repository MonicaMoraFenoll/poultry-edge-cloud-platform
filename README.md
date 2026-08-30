# Poultry Edge-Cloud Platform

## Descripción

Este repositorio contiene la implementación de una plataforma
**Edge-Cloud** para el conteo automático de huevos mediante visión por
computador utilizando modelos YOLO.

La arquitectura separa las responsabilidades entre el procesamiento en
los dispositivos **Edge** y los servicios centralizados utilizados para
la gestión de modelos y los datos:

-   **Edge**: desplegado en cada granja, ejecuta la inferencia diaria,
    mantiene una copia local del modelo y gestiona la transferencia de
    los resultados.
-   **MLflow / Model Registry**: gestiona el versionado y la
    distribución de los modelos utilizados por los dispositivos Edge.
-   **Azure Data Lake Storage Gen2 (ADLS)**: recibe los resultados
    generados en las granjas para su posterior procesamiento en la
    plataforma Cloud.

El objetivo del diseño es utilizar **el mismo código y la misma imagen
Docker en todas las granjas**, modificando únicamente la configuración
asignada a cada dispositivo.

------------------------------------------------------------------------

## Estructura del repositorio

``` text
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
│
├── scripts/
│   ├── generate_mock_images.py
│   ├── generate_mock_egg_results.py
│   └── register_mock_model.py
│
└── README.md
```

### Responsabilidad de las carpetas

  -----------------------------------------------------------------------
  Carpeta                             Descripción
  ----------------------------------- -----------------------------------
  `data/`                             Datos utilizados durante el
                                      desarrollo y resultados simulados.

  `poultry_edge/config/`              Configuración específica de cada
                                      dispositivo/granja.

  `poultry_edge/deployment/`          Scripts y unidades `systemd`
                                      utilizadas para aprovisionar y
                                      ejecutar el Edge.

  `poultry_edge/src/poultry_edge/`    Código Python de inferencia,
                                      gestión de modelos e ingesta.

  `poultry_edge/tests/`               Tests automatizados del componente
                                      Edge.

  `cloud/`                            Componentes de la plataforma Cloud.

  `scripts/`                          Scripts auxiliares para simulación
                                      y validación del prototipo.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 1. Datos simulados

## 1.1. Generación de imágenes simuladas

Para desarrollar y validar el pipeline sin depender inicialmente de las
imágenes de una instalación real, el proyecto incorpora un script para
generar una estructura de imágenes simulada.

Ejemplo:

``` bash
python scripts/generate_mock_images.py \
    --houses 6 \
    --cages-per-house 20 \
    --start-date 2026-06-01 \
    --end-date 2026-06-30
```

La estructura generada sigue el patrón:

``` text
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

Cada imagen representa una captura asociada a una jaula y una fecha. Los
ficheros simulados permiten reproducir la organización que tendría el
almacenamiento local de un dispositivo Edge.

## 1.2. Generación de resultados de inferencia simulados

El script `generate_mock_egg_results.py` genera resultados de inferencia
simulados durante cinco días para las tres granjas, respetando la
estructura de naves y jaulas definida en los datos maestros.

Los datos incorporan:

-   variabilidad productiva entre jaulas y días;
-   una anomalía espacial persistente en una zona concreta de una
    batería;
-   una caída productiva temporal;
-   un pequeño porcentaje de errores técnicos de inferencia.

Estos escenarios permiten validar posteriormente las etapas de limpieza,
contextualización, agregación y detección de anomalías del flujo de
datos.

------------------------------------------------------------------------

# 2. Componente Edge

Cada granja dispone conceptualmente de un dispositivo Edge
independiente. Todos utilizan la misma aplicación y la misma imagen
Docker; las diferencias entre instalaciones se definen mediante el
fichero de configuración asignado al dispositivo.

``` text
poultry_edge/
├── config/
├── deployment/
├── src/
│   └── poultry_edge/
├── tests/
├── Dockerfile
└── pyproject.toml
```

## 2.1. Configuración del Edge

Cada dispositivo utiliza un único fichero YAML:

``` text
poultry_edge/config/
├── farm_01.yml
├── farm_02.yml
└── farm_03.yml
```

El fichero define, entre otros:

-   identificador de la granja;
-   ubicación de las imágenes;
-   directorio de resultados;
-   modelo registrado en MLflow;
-   alias del modelo asignado a la granja;
-   directorio local de modelos;
-   extensiones de imagen soportadas;
-   ubicación de la base de datos local utilizada para mantener el
    estado de las transferencias.

Ejemplo de configuración del modelo:

``` yaml
model:
  registered_name: egg_detector
  alias: farm_01_production
  local_root_directory: /app/models
```

De esta forma, la misma imagen Docker puede desplegarse en diferentes
granjas cambiando únicamente `edge.yaml`.

------------------------------------------------------------------------

# 3. Pipeline de inferencia

## 3.1. Módulos principales

El pipeline está implementado en:

``` text
poultry_edge/src/poultry_edge/
```

  -----------------------------------------------------------------------
  Módulo                              Responsabilidad
  ----------------------------------- -----------------------------------
  `config.py`                         Carga y validación del fichero YAML
                                      asignado al Edge.

  `image_discovery.py`                Descubrimiento de las imágenes
                                      correspondientes a la fecha de
                                      procesamiento.

  `model_loader.py`                   Resolución de la versión activa en
                                      MLflow, sincronización local y
                                      fallback.

  `inference.py`                      Ejecución de la inferencia YOLO
                                      sobre las imágenes descubiertas.

  `output_writer.py`                  Escritura de los resultados de
                                      inferencia en CSV.

  `pipeline.py`                       Orquestación del pipeline diario.

  `main.py`                           Punto de entrada de la aplicación
                                      de inferencia.
  -----------------------------------------------------------------------

## 3.2. Flujo de ejecución

``` text
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

``` text
data/outputs/
└── YYYY/
    └── MM/
        └── DD/
            └── egg_prediction.csv
```

Cada fila representa una imagen procesada e incluye información como:

-   `farm_id`;
-   `house_id`;
-   `cage_id`;
-   fecha de captura y procesamiento;
-   nombre y ruta de la imagen;
-   tamaño del fichero;
-   `egg_count`;
-   confianza;
-   nombre, versión y alias del modelo;
-   fecha de sincronización del modelo;
-   duración de la inferencia;
-   estado de inferencia y mensaje de error.

------------------------------------------------------------------------

# 4. Gestión y distribución de modelos con MLflow

## 4.1. Estrategia de registro

Los modelos se gestionan mediante **MLflow Model Registry**.

En lugar de mantener un modelo registrado diferente para cada granja, se
utiliza un único modelo por tarea:

``` text
egg_detector
```

Cada entrenamiento genera una nueva versión dentro del mismo modelo
registrado.

Las versiones pueden incluir tags descriptivos, por ejemplo:

``` text
farm_id = farm_01
task = egg_detection
model_type = YOLO
mock_model = true
```

Los **tags** se utilizan para aportar trazabilidad y contexto, mientras
que los **aliases** determinan qué versión debe utilizar cada
instalación.

Ejemplo:

``` text
egg_detector
├── version 1 → farm_01_production
├── version 2 → farm_02_production
└── version 3 → farm_03_production
```

Cuando se registra una nueva versión para una granja, el alias
correspondiente puede reasignarse:

``` text
Antes:
farm_01_production → version 1

Después:
farm_01_production → version 4
```

La versión anterior permanece registrada en MLflow, permitiendo mantener
el histórico y realizar un rollback si fuera necesario.

## 4.2. Registro de modelos de prueba

Para validar el mecanismo se utiliza `register_mock_model.py`.

Primero se inicia un servidor MLflow local:

``` bash
mlflow server --host 127.0.0.1 --port 5000
```

En PowerShell puede configurarse:

``` powershell
$env:MLFLOW_TRACKING_URI="http://127.0.0.1:5000"
```

Ejemplo de registro:

``` bash
python scripts/register_mock_model.py \
    --model-path <path_to_model.pt> \
    --farm-id farm_01
```

El script:

1.  registra el artefacto del modelo;
2.  crea una nueva versión de `egg_detector`;
3.  añade metadatos y tags;
4.  asigna el alias `<farm_id>_production`.

## 4.3. Sincronización en el Edge

`model_loader.py` consulta en MLflow la versión asociada al alias
configurado en `edge.yaml`.

Por ejemplo:

``` text
registered_name = egg_detector
alias = farm_01_production
```

El Edge resuelve el alias, identifica la versión activa y la almacena
localmente.

La estructura local sigue el patrón:

``` text
models/
└── egg_detector/
    ├── versions/
    │   ├── 1/
    │   └── 4/
    └── current.json
```

`current.json` mantiene la referencia a la última versión sincronizada
correctamente.

Si MLflow no está disponible temporalmente y existe una versión local
válida, el pipeline puede utilizarla como **fallback**, evitando que una
pérdida de conectividad impida necesariamente la inferencia.

------------------------------------------------------------------------

# 5. Contenedorización

La aplicación Edge se distribuye mediante una imagen Docker común.

El `Dockerfile`:

-   utiliza una imagen base NVIDIA/PyTorch;
-   instala las dependencias del sistema;
-   instala las dependencias Python;
-   instala el paquete `poultry-edge`;
-   contiene tanto la funcionalidad de inferencia como la de ingesta.

El paquete define dos entry points:

``` text
poultry-edge
poultry-edge-upload
```

Por defecto, la imagen ejecuta:

``` dockerfile
CMD ["poultry-edge"]
```

Por tanto, la misma imagen puede utilizarse para dos procesos
independientes:

``` text
MISMA IMAGEN DOCKER
        │
        ├── poultry-edge
        │       └── inferencia
        │
        └── poultry-edge-upload
                └── ingesta
```

No se mantienen dos imágenes Docker diferentes.

------------------------------------------------------------------------

# 6. CI/CD y despliegue del Edge

La arquitectura de CI/CD utiliza **GitHub Actions, Docker y runners
autoalojados**.

Se distinguen tres procesos de despliegue y un proceso operativo:

1.  construcción de la imagen Docker;
2.  aprovisionamiento del dispositivo;
3.  despliegue de una versión;
4.  ejecución programada de los procesos Edge.

## 6.1. Workflows de Githbub Actions

Los procesos de integración, aprovisionamiento y despliegue se automatizan mediante GitHub Actions.

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
| Workflow                          | Responsabilidad                                                                                                              |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `test-edge.yml`                   | Ejecutar automáticamente los tests del componente Edge y validar los cambios realizados en el código.                        |
| `build-edge-image.yml`            | Construir la imagen Docker de la aplicación Edge y publicarla en el registro de contenedores.                                |
| `edge-provisioning.yml`           | Preparar un nuevo dispositivo Edge físico e instalar su configuración, estructura persistente, scripts y unidades `systemd`. |
| `edge-deploy.yml`                 | Desplegar una versión concreta de la imagen Docker sobre un dispositivo Edge previamente aprovisionado.                      |
| `simulated-edge-provisioning.yml` | Reproducir el proceso de aprovisionamiento utilizando directorios locales que simulan diferentes dispositivos Edge.          |
| `simulated-edge-deploy.yml`       | Simular el despliegue de una versión de la aplicación sin necesidad de disponer de los dispositivos Edge físicos.            |


## 6.2. Construcción de la imagen Docker

Workflow:

``` text
.github/workflows/build-edge-image.yml
```

Responsabilidades:

-   construir la imagen Docker;
-   instalar las dependencias;
-   instalar el paquete Python;
-   ejecutar las validaciones definidas en CI;
-   publicar la imagen en GitHub Container Registry (GHCR).

La construcción se realiza en la infraestructura de GitHub Actions y no
requiere utilizar los recursos de los dispositivos Edge.

## 6.3. Aprovisionamiento

El aprovisionamiento se realiza cuando se incorpora un nuevo
dispositivo.

`install_edge.sh` recibe el fichero YAML correspondiente a la granja y
prepara la estructura persistente:

``` text
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

El código Python no se copia directamente al Edge: se distribuye dentro
de la imagen Docker.

Para simulaciones puede utilizarse un directorio de instalación
alternativo. En ese caso, el script crea la estructura local sin
modificar el `systemd` real del equipo.

## 6.4. Despliegue de nuevas versiones

El workflow de despliegue permite seleccionar una versión concreta de la
imagen y desplegarla en un Edge determinado.

El proceso realiza:

-   autenticación en GHCR;
-   descarga (`pull`) de la imagen seleccionada;
-   configuración del Edge para utilizar esa versión en ejecuciones
    posteriores.

Esto permite desplegar una versión inicialmente en una instalación
concreta antes de extenderla al resto.

------------------------------------------------------------------------

# 7. Ejecución automática de la inferencia

La ejecución diaria es independiente del despliegue.

Intervienen:

``` text
poultry-edge.timer
poultry-edge.service
run_edge.sh
```

Flujo:

``` text
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

-   `edge.yaml`;
-   imágenes;
-   resultados;
-   modelos locales.

El contenedor necesita GPU para ejecutar la inferencia.

Al utilizar `docker run --rm`, el contenedor es **efímero**: desaparece
al terminar la ejecución. Los datos importantes permanecen en el host
mediante los directorios montados.

------------------------------------------------------------------------

# 8. Ingesta de resultados hacia Azure

La ingesta se implementa como un proceso **independiente de la
inferencia**.

El objetivo es que una interrupción de conectividad con Azure no impida
generar los resultados localmente.

Flujo general:

``` text
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

Gestiona la base de datos SQLite que mantiene el estado persistente de
las transferencias.

Responsabilidades:

-   inicializar la base de datos;
-   registrar nuevos ficheros como `PENDING`;
-   almacenar el número de intentos;
-   registrar la fecha del último intento;
-   marcar transferencias como `FAILED`;
-   almacenar el último error;
-   marcar transferencias como `UPLOADED`;
-   recuperar registros `PENDING` y `FAILED`.

El estado se almacena fuera del contenedor, en el directorio persistente
`data/state/`.

## 8.2. `upload_discovery.py`

Descubre nuevos `egg_prediction.csv` generados por la inferencia.

Estructura local:

``` text
/app/data/outputs/YYYY/MM/DD/egg_prediction.csv
```

Utiliza el `farm_id` del `edge.yaml` para construir la ruta remota:

``` text
farm_id/YYYY/MM/DD/egg_prediction.csv
```

De esta forma, cada Edge envía únicamente los resultados
correspondientes a su propia granja.

Los nuevos ficheros se registran en SQLite antes de intentar la
transferencia.

## 8.3. `cloud_uploader.py`

Encapsula la comunicación con **Azure Data Lake Storage Gen2**.

Responsabilidades:

-   crear el cliente ADLS;
-   subir el fichero;
-   consultar las propiedades del fichero remoto;
-   verificar la transferencia comparando el tamaño local y remoto;
-   generar un error cuando la verificación falla.

El fichero solo se considera transferido correctamente después de
superar la verificación.

## 8.4. `upload_manager.py`

Orquesta los reintentos.

Recupera los registros con estado:

``` text
PENDING
FAILED
```

y procesa cada fichero de manera independiente.

Resultado:

``` text
PENDING / FAILED ── éxito ──> UPLOADED
PENDING / FAILED ── error ──> FAILED
```

El fallo de un fichero no detiene el procesamiento de los demás.

## 8.5. `upload_results.py`

Es el punto de entrada de la ingesta.

Responsabilidades:

1.  cargar `edge.yaml`;
2.  obtener `farm_id`, `outputs` y `state_database`;
3.  inicializar SQLite;
4.  descubrir nuevos resultados;
5.  crear el cliente ADLS;
6.  procesar `PENDING` y `FAILED`;
7.  registrar el resumen de la ejecución.

El paquete expone este proceso mediante:

``` text
poultry-edge-upload
```

En el prototipo, el nombre de la cuenta de almacenamiento y el
filesystem `landing` se mantienen definidos estáticamente en este
módulo.

## 8.6. `run_upload.sh`

Ejecuta la ingesta dentro de la misma imagen Docker utilizada para
inferencia, sobrescribiendo el comando por defecto:

``` text
docker run ... IMAGE poultry-edge-upload
```

Monta únicamente:

``` text
config  → lectura
outputs → lectura
state   → lectura/escritura
```

La ingesta no requiere GPU.

## 8.7. Automatización con `systemd`

Intervienen:

``` text
poultry-edge-upload.timer
poultry-edge-upload.service
run_upload.sh
```

Flujo:

``` text
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

Inferencia e ingesta crean **contenedores efímeros independientes a
partir de la misma imagen Docker**. Esto permite reintentar
transferencias sin volver a ejecutar la inferencia.

------------------------------------------------------------------------

# 9. Tests y calidad del código

Los tests del componente Edge se encuentran en:

``` text
poultry_edge/tests/
```

Pueden ejecutarse con:

``` bash
pytest
```

Para comprobar la cobertura:

``` bash
pytest --cov=poultry_edge --cov-report=term-missing
```

La validación automatizada se integra en GitHub Actions para detectar
errores cuando se realizan cambios en el código.

Los tests cubren las principales responsabilidades del Edge, incluyendo
configuración, descubrimiento de imágenes, inferencia, sincronización de
modelos, generación de resultados y mecanismos asociados a la ingesta.

------------------------------------------------------------------------

# 10. Resumen de responsabilidades

  -------------------------------------------------------------------------
  Componente                            Responsabilidad
  ------------------------------------- -----------------------------------
  `config.py`                           Configuración específica del Edge.

  `image_discovery.py`                  Localizar las imágenes que deben
                                        procesarse.

  `model_loader.py`                     Resolver, sincronizar y recuperar
                                        modelos desde MLflow.

  `inference.py`                        Ejecutar YOLO.

  `output_writer.py`                    Persistir los resultados diarios.

  `pipeline.py`                         Orquestar la inferencia.

  `main.py`                             Entry point `poultry-edge`.

  `upload_state.py`                     Mantener el estado persistente de
                                        transferencias.

  `upload_discovery.py`                 Detectar nuevos resultados y
                                        construir su ruta remota.

  `cloud_uploader.py`                   Comunicación y verificación con
                                        ADLS.

  `upload_manager.py`                   Procesar y reintentar
                                        transferencias.

  `upload_results.py`                   Orquestar la ingesta.

  `run_edge.sh`                         Crear el contenedor de inferencia.

  `run_upload.sh`                       Crear el contenedor de ingesta.

  `install_edge.sh`                     Preparar una nueva instalación
                                        Edge.

  `poultry-edge.service/timer`          Automatizar la inferencia.

  `poultry-edge-upload.service/timer`   Automatizar la ingesta.
  -------------------------------------------------------------------------

------------------------------------------------------------------------

# 11. Flujo completo del Edge

``` text
                         MLflow Model Registry
                                 │
                     egg_detector + farm alias
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                         EDGE                                │
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
│                         ├── inferencia                      │
│                         └── egg_prediction.csv              │
│                                      │                      │
│                                      ▼                      │
│                               data/outputs                  │
│                                      │                      │
│                                      ▼                      │
│                        poultry-edge-upload.timer             │
│                                      │                      │
│                                      ▼                      │
│                       run_upload.sh → Docker                 │
│                                      │                      │
│                                      ▼                      │
│                           poultry-edge-upload                │
│                                      │                      │
│                         SQLite state + reintentos            │
└──────────────────────────────────────┼──────────────────────┘
                                       │
                                       ▼
                         Azure Data Lake Storage
                                       │
                                       ▼
                                    Landing
```

La arquitectura mantiene separados el ciclo de inferencia, la
distribución de modelos y la transferencia de resultados, conservando
localmente los elementos necesarios para tolerar interrupciones
temporales de conectividad.
