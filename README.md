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

CI/CD

build-edge-image.yml (CI): construye y publica la imagen Docker.
edge-provisioning.yml: prepara un Edge nuevo.
edge-deploy.yml: despliega una versión concreta en una granja seleccionada.
run_edge.sh + systemd.service + systemd.timer: ejecutan automáticamente la inferencia diaria.

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

# Próximos pasos

Las siguientes fases del proyecto consistirán en:

1. Simular la llegada diaria de nuevas imágenes al dispositivo Edge.
2. Implementar un pipeline de inferencia simulado que genere el número de huevos detectados por jaula.
3. Desarrollar la aplicación Edge encargada del procesamiento automático.
4. Sincronizar los resultados con una plataforma Cloud.
5. Desarrollar un dashboard para la visualización y análisis de los fenotipos digitales obtenidos.