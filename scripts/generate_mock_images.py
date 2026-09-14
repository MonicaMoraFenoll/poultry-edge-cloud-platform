import argparse

from collections.abc import Iterator

from datetime import date, datetime, timedelta

from pathlib import Path


def parse_date(value: str) -> date:
    """
    Convert a string in YYYY-MM-DD format to a date.

    Parameters
    ----------
    value:
        Date string provided through the command-line interface.

    Returns
    -------
    date
        Parsed calendar date.

    Raises
    ------
    argparse.ArgumentTypeError
        If the input value does not follow the YYYY-MM-DD format.
    """

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()

    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{value}'. Expected format: YYYY-MM-DD."
        ) from error


def generate_dates(
    start_date: date,
    end_date: date,
) -> Iterator[date]:
    """
    Generate all dates between two boundaries, inclusive.

    Parameters
    ----------
    start_date:
        First date to generate.

    end_date:
        Last date to generate.

    Yields
    ------
    date
        Each date in chronological order from start_date to end_date.
    """

    current_date = start_date

    while current_date <= end_date:
        yield current_date

        current_date += timedelta(days=1)


def build_day_directory(
    output_directory: Path,
    house_id: str,
    capture_date: date,
) -> Path:
    """
    Build the directory for one house and capture date.

    Parameters
    ----------
    output_directory:
        Root directory where the simulated images are stored.

    house_id:
        Identifier of the simulated poultry house.

    capture_date:
        Date associated with the generated images.

    Returns
    -------
    Path
        Directory following the house/year/month/day hierarchy.

    Examples
    --------
    data/simulated/house_01/2026/06/30
    """

    return (
        output_directory
        / house_id
        / f"{capture_date.year:04d}"
        / f"{capture_date.month:02d}"
        / f"{capture_date.day:02d}"
    )


def generate_mock_images(
    output_directory: Path,
    number_of_houses: int,
    cages_per_house: int,
    start_date: date,
    end_date: date,
) -> None:
    """
    Generate empty mock cage image files for one farm.

    Parameters
    ----------
    output_directory:
        Root directory where the mock image hierarchy is created.

    number_of_houses:
        Number of simulated poultry houses.

    cages_per_house:
        Number of cage image files generated per house and day.

    start_date:
        First capture date to generate.

    end_date:
        Last capture date to generate.
    """

    total_files = 0

    for house_number in range(1, number_of_houses + 1):
        house_id = f"house_{house_number:02d}"

        for capture_date in generate_dates(start_date, end_date):

            # Store images using the same year/month/day hierarchy
            # expected by the Edge image-discovery component.
            day_directory = build_day_directory(
                output_directory=output_directory,
                house_id=house_id,
                capture_date=capture_date,
            )

            # Create the complete directory hierarchy if it does not exist.
            day_directory.mkdir(parents=True, exist_ok=True)

            for cage_number in range(1, cages_per_house + 1):
                cage_id = f"cage_{cage_number:03d}"

                image_path = day_directory / f"{cage_id}.jpg"

                # Create an empty file that simulates a cage image.
                image_path.touch(exist_ok=True)

                total_files += 1

    number_of_days = (end_date - start_date).days + 1

    expected_files = (
        number_of_houses
        * number_of_days
        * cages_per_house
    )

    print("Mock images generated successfully")

    print(f"Houses: {number_of_houses}")

    print(f"Days: {number_of_days}")

    print(f"Cages per house: {cages_per_house}")

    print(f"Files generated: {total_files}")

    print(f"Expected files: {expected_files}")

    print(f"Output directory: {output_directory.resolve()}")


def build_parser() -> argparse.ArgumentParser:
    """
    Create the command-line interface.

    Returns
    -------
    argparse.ArgumentParser
        Argument parser containing the options required to generate
        the simulated farm image dataset.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Generate empty mock cage images for one poultry farm edge."
        )
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/simulated"),
        help="Directory where the mock images will be generated.",
    )

    parser.add_argument(
        "--houses",
        type=int,
        default=6,
        help="Number of houses in the farm.",
    )

    parser.add_argument(
        "--cages-per-house",
        type=int,
        default=20,
        help="Number of cage images generated per house and day.",
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        required=True,
        help="First date to generate, in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
        required=True,
        help="Last date to generate, in YYYY-MM-DD format.",
    )

    return parser


def validate_arguments(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    """
    Validate command-line arguments.

    Parameters
    ----------
    parser:
        Argument parser used to report invalid input.

    args:
        Parsed command-line arguments.
    """

    if args.houses <= 0:
        parser.error("--houses must be greater than zero")

    if args.cages_per_house <= 0:
        parser.error("--cages-per-house must be greater than zero")

    if args.end_date < args.start_date:
        parser.error("--end-date must be equal to or after --start-date")


def main() -> None:
    """
    Parse command-line arguments and generate the mock image files.
    """

    parser = build_parser()

    args = parser.parse_args()

    validate_arguments(parser, args)

    generate_mock_images(
        output_directory=args.output,
        number_of_houses=args.houses,
        cages_per_house=args.cages_per_house,
        start_date=args.start_date,
        end_date=args.end_date,
    )


if __name__ == "__main__":
    main()