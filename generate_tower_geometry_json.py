#!/usr/bin/env python3
"""Generate one tower floorplate JSON per row in an outrigger tower CSV.

Usage:
    python generate_tower_geometry_json.py data/outrigger_tower_list.csv
    python generate_tower_geometry_json.py towers.csv --output-dir generated_json

The output follows the 1.0 tower floorplate format (units, floor_sequence,
and floor_types). The CSV format has no material, member sizing, or detailed
structural layout fields, so geometry and member properties below are explicit
preliminary assumptions, not engineered design results:
  * centered rectangular floor plate and core using the CSV dimensions;
  * four 12 in concrete shear walls around the core;
  * 36 x 36 in concrete columns around the perimeter, approximately 12 ft apart,
    inset 1.5 ft from the floor plate edge;
  * concrete properties Fy=4,000 psi, E=3,600,000 psi, Poisson ratio=0.20;
  * identical floor type at every level, with uniform story heights derived
    from total tower height / floor count so the sequence sums to CSV height.

Location, program, aspect ratio, area, and the rounded F2F input are not added
to the JSON because the referenced format has no metadata fields. Output names
are derived from the Name field (e.g. Tower A -> tower_a.json).
"""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

REQUIRED_COLUMNS = (
    "Name",
    "Height (ft)",
    "Core A (ft)",
    "Core B (ft)",
    "Footprint A (ft)",
    "Footprint B (ft)",
    "Floors",
)

# Assumed, editable preliminary properties (not provided by the CSV).
CONCRETE_FY_PSI = 4000
CONCRETE_E_PSI = 3_600_000
CONCRETE_POISSON = 0.20
WALL_THICKNESS_IN = 12.0
COLUMN_SIZE_IN = 36.0
COLUMN_SPACING_FT = 12.0
COLUMN_EDGE_INSET_FT = 1.5


def number(row, field, row_number):
    value = row.get(field, "")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"row {row_number}: {field!r} must be numeric; got {value!r}")
    if not math.isfinite(result):
        raise ValueError(f"row {row_number}: {field!r} must be a finite number")
    return result


def clean_number(value):
    """Round coordinate noise while preserving useful decimal precision."""
    rounded = round(float(value), 6)
    return int(rounded) if rounded.is_integer() else rounded


def tower_filename(name):
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    if not slug:
        raise ValueError("tower Name must contain at least one letter or number")
    return f"{slug}.json"


def segments_for(length_ft):
    clear_length = max(0.0, length_ft - 2 * COLUMN_EDGE_INSET_FT)
    return max(1, int(math.floor(clear_length / COLUMN_SPACING_FT + 0.5)))


def perimeter_column_points(width_ft, depth_ft):
    """Return unique perimeter points, inset from the plate edge."""
    x0 = -width_ft / 2 + COLUMN_EDGE_INSET_FT
    x1 = width_ft / 2 - COLUMN_EDGE_INSET_FT
    y0 = -depth_ft / 2 + COLUMN_EDGE_INSET_FT
    y1 = depth_ft / 2 - COLUMN_EDGE_INSET_FT
    nx = segments_for(width_ft)
    ny = segments_for(depth_ft)
    points = []

    # Bottom and top rows include corners.
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        points.append((x, y0))
    for i in range(nx + 1):
        x = x0 + (x1 - x0) * i / nx
        points.append((x, y1))
    # Side rows omit corners already included above.
    for i in range(1, ny):
        y = y0 + (y1 - y0) * i / ny
        points.append((x0, y))
        points.append((x1, y))

    # Remove any coincident coordinates and keep output order deterministic.
    unique = []
    seen = set()
    for x, y in points:
        key = (round(x, 8), round(y, 8))
        if key not in seen:
            seen.add(key)
            unique.append((clean_number(x), clean_number(y)))
    return unique


def build_tower(row, row_number):
    name = (row.get("Name") or "").strip()
    if not name:
        raise ValueError(f"row {row_number}: Name is required")

    height = number(row, "Height (ft)", row_number)
    core_a = number(row, "Core A (ft)", row_number)
    core_b = number(row, "Core B (ft)", row_number)
    footprint_a = number(row, "Footprint A (ft)", row_number)
    footprint_b = number(row, "Footprint B (ft)", row_number)
    floor_value = number(row, "Floors", row_number)
    floors = int(floor_value)

    if height <= 0 or core_a <= 0 or core_b <= 0 or footprint_a <= 0 or footprint_b <= 0:
        raise ValueError(f"row {row_number}: height and plan dimensions must be positive")
    if floors <= 0 or floor_value != floors:
        raise ValueError(f"row {row_number}: Floors must be a positive whole number")
    if core_a > footprint_a or core_b > footprint_b:
        raise ValueError(f"row {row_number}: core dimensions cannot exceed footprint dimensions")
    if min(footprint_a, footprint_b) <= 2 * COLUMN_EDGE_INSET_FT:
        raise ValueError(f"row {row_number}: footprint is too small for the assumed column inset")

    # Core corner ordering is counterclockwise from lower left.
    core_nodes = [
        {"id": "S1", "x": clean_number(-core_a / 2), "y": clean_number(-core_b / 2)},
        {"id": "S2", "x": clean_number(core_a / 2), "y": clean_number(-core_b / 2)},
        {"id": "S3", "x": clean_number(core_a / 2), "y": clean_number(core_b / 2)},
        {"id": "S4", "x": clean_number(-core_a / 2), "y": clean_number(core_b / 2)},
    ]
    col_points = perimeter_column_points(footprint_a, footprint_b)
    column_nodes = [
        {"id": f"C{i}", "x": x, "y": y}
        for i, (x, y) in enumerate(col_points, start=1)
    ]

    elements = []
    wall_edges = [("S1", "S2", core_a), ("S2", "S3", core_b),
                  ("S3", "S4", core_a), ("S4", "S1", core_b)]
    for i, (start, end, wall_length_ft) in enumerate(wall_edges, start=1):
        elements.append({
            "id": f"W{i}",
            "type": "shear_wall",
            "nodes": [start, end],
            "material_name": "Concrete",
            "section_name": f"CoreWall-{clean_number(WALL_THICKNESS_IN)}in",
            "Fy": CONCRETE_FY_PSI,
            "E": CONCRETE_E_PSI,
            "poisson_ratio": CONCRETE_POISSON,
            "section_dims": {
                "width": clean_number(WALL_THICKNESS_IN),
                "depth": clean_number(wall_length_ft * 12),
            },
        })

    for i, node in enumerate(column_nodes, start=1):
        elements.append({
            "id": f"COL{i}",
            "type": "column",
            "nodes": [node["id"]],
            "material_name": "Concrete",
            "section_name": f"Column-{clean_number(COLUMN_SIZE_IN)}x{clean_number(COLUMN_SIZE_IN)}in",
            "Fy": CONCRETE_FY_PSI,
            "E": CONCRETE_E_PSI,
            "poisson_ratio": CONCRETE_POISSON,
            "section_dims": {
                "width": clean_number(COLUMN_SIZE_IN),
                "depth": clean_number(COLUMN_SIZE_IN),
            },
        })

    plate_a = footprint_a / 2
    plate_b = footprint_b / 2
    plate_nodes = [
        {"id": "P1", "x": clean_number(-plate_a), "y": clean_number(-plate_b)},
        {"id": "P2", "x": clean_number(plate_a), "y": clean_number(-plate_b)},
        {"id": "P3", "x": clean_number(plate_a), "y": clean_number(plate_b)},
        {"id": "P4", "x": clean_number(-plate_a), "y": clean_number(plate_b)},
    ]

    story_height = height / floors
    data = {
        "format_version": "1.0",
        "units": {
            "coordinates": "ft",
            "floor_height": "ft",
            "section_dimensions": "in",
            "Fy": "psi",
            "E": "psi",
        },
        "floor_sequence": [
            {"type": "A", "floor_height": story_height}
            for _ in range(floors)
        ],
        "floor_types": {
            "A": {
                "structural_nodes": core_nodes + column_nodes,
                "structural_elements": elements,
                "floor_plate": {
                    "boundary_nodes": plate_nodes,
                    "boundary_loop": ["P1", "P2", "P3", "P4"],
                },
            }
        },
    }
    return name, data


def validate_output(data, expected_floors, expected_height, label):
    """Check the generated object against the documented floorplate format."""
    required_units = {
        "coordinates": "ft",
        "floor_height": "ft",
        "section_dimensions": "in",
        "Fy": "psi",
        "E": "psi",
    }
    if data.get("format_version") != "1.0":
        raise ValueError(f"{label}: format_version must be '1.0'")
    if data.get("units") != required_units:
        raise ValueError(f"{label}: units do not match the documented format")
    if not isinstance(data.get("floor_types"), dict) or not data["floor_types"]:
        raise ValueError(f"{label}: floor_types must be a non-empty object")
    if not isinstance(data.get("floor_sequence"), list):
        raise ValueError(f"{label}: floor_sequence must be an array")
    if len(data["floor_sequence"]) != expected_floors:
        raise ValueError(f"{label}: generated floor count does not match CSV")
    for entry in data["floor_sequence"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("type"), str):
            raise ValueError(f"{label}: each floor sequence entry needs a type string")
        try:
            floor_height = float(entry["floor_height"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"{label}: each floor sequence entry needs a numeric floor_height")
        if not math.isfinite(floor_height) or floor_height <= 0:
            raise ValueError(f"{label}: floor_height values must be positive and finite")
    total_height = sum(f["floor_height"] for f in data["floor_sequence"])
    if not math.isclose(total_height, expected_height, rel_tol=0, abs_tol=1e-5):
        raise ValueError(f"{label}: floor heights sum to {total_height}, expected {expected_height}")

    floor_type = data["floor_types"]["A"]
    for key in ("structural_nodes", "structural_elements", "floor_plate"):
        if key not in floor_type:
            raise ValueError(f"{label}: floor type A is missing {key}")
    if not isinstance(floor_type["structural_nodes"], list):
        raise ValueError(f"{label}: structural_nodes must be an array")
    node_ids = {node["id"] for node in floor_type["structural_nodes"]}
    if len(node_ids) != len(floor_type["structural_nodes"]):
        raise ValueError(f"{label}: duplicate structural node IDs")
    for element in floor_type["structural_elements"]:
        valid_node_counts = {"column": 1, "beam": 2, "shear_wall": 2, "outrigger": 2}
        if element.get("type") not in valid_node_counts:
            raise ValueError(f"{label}: {element.get('id', 'element')} has an unsupported type")
        if len(element.get("nodes", [])) != valid_node_counts[element["type"]]:
            raise ValueError(f"{label}: {element.get('id', 'element')} has the wrong number of node references")
        for key in ("id", "material_name", "section_name", "Fy", "E", "poisson_ratio", "section_dims"):
            if key not in element:
                raise ValueError(f"{label}: {element.get('id', 'element')} is missing {key}")
        dims = element["section_dims"]
        if not isinstance(dims, dict) or any(
            key not in dims or not isinstance(dims[key], (int, float)) or
            not math.isfinite(dims[key]) or dims[key] <= 0
            for key in ("width", "depth")
        ):
            raise ValueError(f"{label}: {element['id']} has invalid section dimensions")
        missing = set(element["nodes"]) - node_ids
        if missing:
            raise ValueError(f"{label}: {element['id']} references missing node(s): {sorted(missing)}")
    plate = floor_type["floor_plate"]
    if not isinstance(plate, dict) or not isinstance(plate.get("boundary_nodes"), list):
        raise ValueError(f"{label}: floor_plate needs a boundary_nodes array")
    boundary_ids = {node["id"] for node in plate["boundary_nodes"]}
    loop = plate.get("boundary_loop")
    if not isinstance(loop, list) or len(loop) < 3 or len(set(loop)) != len(loop):
        raise ValueError(f"{label}: boundary_loop must have at least three unique node IDs")
    if set(loop) != boundary_ids:
        raise ValueError(f"{label}: boundary_loop must reference every boundary node exactly once")
    for entry in data["floor_sequence"]:
        if entry["type"] not in data["floor_types"]:
            raise ValueError(f"{label}: floor sequence references missing type {entry['type']!r}")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "input_csv",
        type=Path,
        metavar="INPUT_CSV",
        help="required path to the .csv file containing one tower per row",
    )
    parser.add_argument(
        "--output-dir", "-o", type=Path,
        help="directory for generated JSON files (default: <CSV directory>/tower_floorplate_json)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_csv = args.input_csv.expanduser().resolve()
    if input_csv.suffix.lower() != ".csv":
        print(f"error: input must be a .csv file: {input_csv}", file=sys.stderr)
        return 2
    if not input_csv.is_file():
        print(f"error: input CSV not found: {input_csv}", file=sys.stderr)
        return 2
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else input_csv.parent / "tower_floorplate_json"

    try:
        with input_csv.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if not reader.fieldnames:
                raise ValueError("CSV is empty or has no header row")
            missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
            if missing:
                raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")
            rows = list(reader)
        if not rows:
            raise ValueError("CSV contains no tower rows")

        prepared = []
        filenames = set()
        for row_number, row in enumerate(rows, start=2):
            name, data = build_tower(row, row_number)
            filename = tower_filename(name)
            if filename in filenames:
                raise ValueError(f"duplicate tower name would overwrite output: {filename}")
            filenames.add(filename)
            height = number(row, "Height (ft)", row_number)
            floors = int(number(row, "Floors", row_number))
            validate_output(data, floors, height, name)
            prepared.append((name, filename, data))

        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"JSON output location: {output_dir}")
        for name, filename, data in prepared:
            path = output_dir / filename
            with path.open("w", encoding="utf-8", newline="\n") as json_file:
                json.dump(data, json_file, indent=2, allow_nan=False)
                json_file.write("\n")
            # Re-open to ensure each written file is valid JSON.
            with path.open("r", encoding="utf-8") as json_file:
                saved = json.load(json_file)
            validate_output(saved, len(saved["floor_sequence"]),
                            sum(f["floor_height"] for f in saved["floor_sequence"]), name)
            print(f"Wrote {path}")
        print(f"Generated {len(prepared)} tower JSON file(s) in {output_dir}")
        return 0
    except (OSError, ValueError, csv.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
