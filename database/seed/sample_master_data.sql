USE poultry_master_data;


-- ============================================================
-- FARMS
-- ============================================================

INSERT INTO farm (
    name,
    location
)
VALUES
    ('farm_01', 'Spain'),
    ('farm_02', 'Scotland'),
    ('farm_03', 'Canada');


-- ============================================================
-- HOUSES
-- ============================================================

INSERT INTO house (
    farm_id,
    house_number
)
VALUES
    -- farm_01
    (1, 1),
    (1, 2),

    -- farm_02
    (2, 1),
    (2, 2),

    -- farm_03
    (3, 1),
    (3, 2);


-- ============================================================
-- BATTERIES
-- ============================================================

INSERT INTO battery (
    house_id,
    battery_number,
    number_of_levels,
    cages_per_side
)
VALUES
    -- farm_01 - house 1
    (1, 1, 2, 250),
    (1, 2, 3, 300),
    (1, 3, 4, 400),
    (1, 4, 3, 500),

    -- farm_01 - house 2
    (2, 1, 2, 300),
    (2, 2, 3, 400),
    (2, 3, 4, 500),

    -- farm_02 - house 1
    (3, 1, 3, 250),
    (3, 2, 4, 350),
    (3, 3, 2, 500),

    -- farm_02 - house 2
    (4, 1, 2, 250),
    (4, 2, 3, 350),
    (4, 3, 4, 450),
    (4, 4, 2, 500),

    -- farm_03 - house 1
    (5, 1, 4, 250),
    (5, 2, 3, 300),
    (5, 3, 2, 400),
    (5, 4, 4, 500),

    -- farm_03 - house 2
    (6, 1, 2, 300),
    (6, 2, 3, 400),
    (6, 3, 4, 500);


-- ============================================================
-- CAGES
-- ============================================================
-- cage_id starts at 1000 for each house.
-- Cage identifiers continue across batteries in the same house,
-- so cage_id never repeats inside one house.
-- The same cage_id may appear in a different house.


WITH RECURSIVE numbers AS (
    SELECT 1 AS n

    UNION ALL

    SELECT n + 1
    FROM numbers
    WHERE n < 500
),

levels AS (
    SELECT 1 AS level

    UNION ALL

    SELECT level + 1
    FROM levels
    WHERE level < 4
),

sides AS (
    SELECT
        'FRONT' AS side,
        0 AS side_order

    UNION ALL

    SELECT
        'BACK',
        1
),

battery_offsets AS (
    SELECT
        b.id AS battery_id,
        b.house_id,
        b.battery_number,
        b.number_of_levels,
        b.cages_per_side,

        COALESCE(
            SUM(
                b.number_of_levels
                * 2
                * b.cages_per_side
            ) OVER (
                PARTITION BY b.house_id
                ORDER BY b.battery_number
                ROWS BETWEEN UNBOUNDED PRECEDING
                AND 1 PRECEDING
            ),
            0
        ) AS previous_cages

    FROM battery b
),

generated_cages AS (
    SELECT
        b.battery_id,

        1000
        + b.previous_cages
        + (
            (
                (l.level - 1) * 2
                + s.side_order
            ) * b.cages_per_side
        )
        + (n.n - 1) AS cage_id,

        l.level,
        s.side,
        s.side_order,
        n.n AS position

    FROM battery_offsets b

    JOIN levels l
        ON l.level <= b.number_of_levels

    CROSS JOIN sides s

    JOIN numbers n
        ON n.n <= b.cages_per_side
)

INSERT INTO cage (
    battery_id,
    cage_id,
    level,
    side,
    position
)
SELECT
    battery_id,
    cage_id,
    level,
    side,
    position
FROM generated_cages
ORDER BY
    battery_id,
    level,
    side_order,
    position;