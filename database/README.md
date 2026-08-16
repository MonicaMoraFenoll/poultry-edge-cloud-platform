# Base de datos de datos maestros avícolas

## Descripción

Este módulo contiene la base de datos relacional utilizada para gestionar los datos maestros asociados a las explotaciones avícolas.

El objetivo de la base de datos es proporcionar el contexto físico y jerárquico necesario para interpretar los fenotipos digitales generados por la plataforma, como el número de huevos detectados por jaula.

```text
Granja
 └── Nave
      └── Batería
           └── Jaula
```

## Modelo de datos

### Granja (`farm`)

Representa una explotación avícola.

Principales atributos:

- `id`: clave primaria interna.
- `name`: nombre de la granja.
- `location`: localización de la granja.

### Nave (`house`)

Representa una nave perteneciente a una granja.

Principales atributos:

- `id`: clave primaria interna.
- `farm_id`: referencia a la granja a la que pertenece.
- `house_number`: número de la nave dentro de la granja.

El número de nave es único dentro de una misma granja, pero puede repetirse entre granjas diferentes.

### Batería (`battery`)

Representa una batería de jaulas situada dentro de una nave.

Principales atributos:

- `id`: clave primaria interna.
- `house_id`: referencia a la nave a la que pertenece.
- `battery_number`: número de batería dentro de la nave.
- `number_of_levels`: número de niveles verticales de la batería.
- `cages_per_side`: número de jaulas por cada lado de la batería.

Las baterías se identifican mediante los números del 1 al 4. Una nave puede disponer de tres o cuatro baterías.

Se considera que ambos lados de una batería contienen el mismo número de jaulas, evitando almacenar información redundante.

### Jaula (`cage`)

Representa la unidad física mínima de la instalación.

Principales atributos:

- `id`: clave primaria interna.
- `battery_id`: referencia a la batería a la que pertenece.
- `cage_id`: identificador operativo de la jaula.
- `level`: nivel vertical de la jaula dentro de la batería.
- `side`: lado de la batería (`FRONT` o `BACK`).
- `position`: posición longitudinal de la jaula dentro de la batería.

La posición física de una jaula queda definida por su batería, nivel, lado y posición.

El `cage_id` es único dentro de una nave, aunque puede repetirse en naves diferentes.

## Relaciones

El modelo utiliza relaciones uno a muchos:

```text
FARM    1 ───── N HOUSE
HOUSE   1 ───── N BATTERY
BATTERY 1 ───── N CAGE
```

De esta forma, a partir de una jaula es posible recuperar todo su contexto físico:

```text
Jaula → Batería → Nave → Granja → Localización
```

## Estructura del módulo

```text
database/
├── README.md
├── schema/
│   └── 001_create_master_data.sql
└── seed/
    └── sample_master_data.sql
```

- `schema/001_create_master_data.sql`: define el esquema relacional, las claves primarias y foráneas y las restricciones de integridad.
- `seed/sample_master_data.sql`: genera datos maestros ficticios para realizar pruebas y demostrar el funcionamiento del modelo.

## Datos de ejemplo

El conjunto de datos de ejemplo contiene tres granjas ficticias:

- `farm_01` — España
- `farm_02` — Escocia
- `farm_03` — Canadá

Cada granja contiene varias naves y baterías con diferentes configuraciones físicas.

Las baterías pueden disponer de entre 2 y 4 niveles y hasta 500 jaulas por lado.

Los identificadores de jaula del conjunto de ejemplo se generan secuencialmente dentro de cada nave, comenzando en `1000`. Por tanto, un mismo `cage_id` puede aparecer en naves diferentes, pero no se repite dentro de una misma nave.

## Finalidad

El modelo de datos maestros permite asociar los fenotipos digitales generados por la plataforma con el contexto físico en el que se han obtenido.

Por ejemplo, un fenotipo correspondiente al número de huevos detectados en una jaula podrá posteriormente contextualizarse y analizarse según:

- granja y localización;
- nave;
- batería;
- nivel de altura;
- lado de la batería;
- posición longitudinal.

Esta estructura permite realizar análisis espaciales de los fenotipos generados sin almacenar información física redundante en los propios registros de fenotipos.