CREATE TABLE farm (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    location VARCHAR(150) NOT NULL
);

CREATE TABLE house (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    farm_id INT NOT NULL,
    house_number INT NOT NULL,

    CONSTRAINT fk_house_farm
        FOREIGN KEY (farm_id)
        REFERENCES farm(id),

    CONSTRAINT uq_house
        UNIQUE (farm_id, house_number)
);

CREATE TABLE battery (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    house_id INT NOT NULL,
    battery_number INT NOT NULL,
    number_of_levels INT NOT NULL,
    cages_per_side INT NOT NULL,

    CONSTRAINT fk_battery_house
        FOREIGN KEY (house_id)
        REFERENCES house(id),

    CONSTRAINT uq_battery
        UNIQUE (house_id, battery_number),

    CONSTRAINT chk_number_of_levels
        CHECK (number_of_levels > 0),

    CONSTRAINT chk_cages_per_side
        CHECK (cages_per_side > 0)
);

CREATE TABLE cage (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    battery_id INT NOT NULL,
    cage_id INT NOT NULL,
    level INT NOT NULL,
    side VARCHAR(10) NOT NULL,
    position INT NOT NULL,

    CONSTRAINT fk_cage_battery
        FOREIGN KEY (battery_id)
        REFERENCES battery(id),

    CONSTRAINT uq_cage_position
        UNIQUE (battery_id, level, side, position),

    CONSTRAINT chk_cage_level
        CHECK (level > 0),

    CONSTRAINT chk_cage_position
        CHECK (position > 0),

    CONSTRAINT chk_cage_side
        CHECK (side IN ('FRONT', 'BACK'))
);