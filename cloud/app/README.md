# Dashboard de Streamlit

Esta carpeta contiene la aplicación local utilizada para visualizar la producción y las anomalías detectadas.

## Datos esperados

Desde la raíz del repositorio, primero ejecuta:

```bash
python scripts/generate_data_streamlit.py
```

Este script genera:

```text
data/dashboard/production_dashboard.csv
data/dashboard/df_detected_anomalies.csv
```

## Instalación de dependencias

```bash
pip install -r cloud/app/requirements.txt
```

## Ejecución de la aplicación

Desde la raíz del repositorio:

```bash
streamlit run cloud/app/app.py
```

La aplicación contiene dos vistas principales:

- **Producción**: permite seleccionar la granja y el día, visualizar los principales indicadores productivos, consultar la producción por batería, analizar la evolución temporal y revisar la producción espacial mediante mapas de calor.

- **Anomalías**: permite consultar las anomalías temporales y espaciales detectadas, identificar las granjas y ubicaciones afectadas y revisar en detalle las zonas anómalas dentro de cada batería.

## Estructura de datos utilizada

La aplicación utiliza dos ficheros:

```text
data/dashboard/
├── production_dashboard.csv
└── df_detected_anomalies.csv
```

`production_dashboard.csv` contiene los datos de producción procesados y enriquecidos con la estructura física de la granja, incluyendo información de:

```text
granja
nave
batería
nivel
lado
grupo de posición
fecha
```

También incluye indicadores como la producción media, la tasa de registros con cero huevos, la tasa de errores de inferencia y la comparación con el comportamiento histórico.

`df_detected_anomalies.csv` contiene únicamente las anomalías detectadas por el proceso analítico, diferenciando entre:

- anomalías temporales, cuando una batería presenta un comportamiento diferente respecto a su propio histórico;
- anomalías espaciales, cuando una zona concreta presenta un comportamiento diferente respecto al resto de la batería.

## Objetivo de la aplicación

La vista de producción permite responder rápidamente a preguntas como:

- ¿Cómo ha ido la producción de una granja en un día concreto?
- ¿Qué naves o baterías presentan menor producción?
- ¿Cómo está evolucionando una batería respecto a los días anteriores?
- ¿Existe alguna zona concreta dentro de la batería con un comportamiento diferente?

La vista de anomalías permite localizar de forma rápida los casos que requieren atención y consultar su ubicación dentro de la estructura productiva.
