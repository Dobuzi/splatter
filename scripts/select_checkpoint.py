#!/usr/bin/env python3
import glob
import json
import math
import re
import struct
import sys
from pathlib import Path

PLY_SCALARS = {
    "char": ("b", True),
    "int8": ("b", True),
    "uchar": ("B", True),
    "uint8": ("B", True),
    "short": ("h", True),
    "int16": ("h", True),
    "ushort": ("H", True),
    "uint16": ("H", True),
    "int": ("i", True),
    "int32": ("i", True),
    "uint": ("I", True),
    "uint32": ("I", True),
    "float": ("f", False),
    "float32": ("f", False),
    "double": ("d", False),
    "float64": ("d", False),
}


def usage():
    print("Usage: scripts/select_checkpoint.py <ply-prefix-or-file>", file=sys.stderr)


def checkpoint_iteration(path):
    match = re.search(r"_(\d+)\.ply$", path.name)
    if match:
        return int(match.group(1))
    match = re.search(r"-(\d+)(?:-d\d+)?\.ply$", path.name)
    if match:
        return int(match.group(1))
    return 0


def read_header(path):
    header = []
    header_bytes = 0
    with path.open("rb") as handle:
        while True:
            raw = handle.readline()
            if not raw:
                break
            header_bytes += len(raw)
            line = raw.decode("ascii", errors="replace").strip()
            header.append(line)
            if line == "end_header":
                break
    return header, header_bytes


def parse_header(header):
    file_format = "ascii"
    vertex_count = 0
    properties = []
    in_vertex = False

    for line in header:
        if line.startswith("format "):
            file_format = line.split()[1]
        elif line.startswith("element "):
            parts = line.split()
            in_vertex = parts[1] == "vertex"
            if in_vertex:
                vertex_count = int(parts[2])
        elif in_vertex and line.startswith("property "):
            parts = line.split()
            if len(parts) >= 3 and parts[1] != "list":
                properties.append((parts[1], parts[2]))
            elif len(parts) >= 5 and parts[1] == "list":
                return file_format, vertex_count, properties, f"unsupported-list-property:{parts[-1]}"

    return file_format, vertex_count, properties, None


def inspect_ascii_ply(path, vertex_count, properties, header_bytes):
    checked = 0
    bad_rows = 0

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(header_bytes)
        for line in handle:
            if checked >= vertex_count:
                break
            values = line.split()
            for value in values:
                try:
                    number = float(value)
                except ValueError:
                    bad_rows += 1
                    break
                if not math.isfinite(number):
                    bad_rows += 1
                    break
            checked += 1

    return inspection_result(path, vertex_count, properties, checked, bad_rows)


def inspect_binary_ply(path, file_format, vertex_count, properties, header_bytes):
    endian = "<" if file_format == "binary_little_endian" else ">"
    struct_parts = []
    float_indexes = []

    for index, (property_type, _name) in enumerate(properties):
        if property_type not in PLY_SCALARS:
            return {
                "path": str(path),
                "finite": False,
                "reason": f"unsupported-property-type:{property_type}",
                "vertices": vertex_count,
                "checked_vertices": 0,
                "bad_rows": 0,
                "iteration": checkpoint_iteration(path),
                "properties": len(properties),
                "format": file_format,
            }
        code, is_integral = PLY_SCALARS[property_type]
        struct_parts.append(code)
        if not is_integral:
            float_indexes.append(index)

    vertex_struct = struct.Struct(endian + "".join(struct_parts))
    checked = 0
    bad_rows = 0

    with path.open("rb") as handle:
        handle.seek(header_bytes)
        for _ in range(vertex_count):
            row = handle.read(vertex_struct.size)
            if len(row) != vertex_struct.size:
                bad_rows += 1
                break
            values = vertex_struct.unpack(row)
            if any(not math.isfinite(values[index]) for index in float_indexes):
                bad_rows += 1
            checked += 1

    return inspection_result(path, vertex_count, properties, checked, bad_rows, file_format)


def inspection_result(path, vertex_count, properties, checked, bad_rows, file_format="ascii"):
    return {
        "path": str(path),
        "finite": bad_rows == 0 and checked == vertex_count,
        "reason": "ok" if bad_rows == 0 else "nan-or-inf",
        "vertices": vertex_count,
        "checked_vertices": checked,
        "bad_rows": bad_rows,
        "iteration": checkpoint_iteration(path),
        "properties": len(properties),
        "format": file_format,
    }


def inspect_ply(path):
    header, header_bytes = read_header(path)
    file_format, vertex_count, properties, reason = parse_header(header)

    if reason:
        return {"path": str(path), "finite": False, "reason": reason}
    if file_format == "ascii":
        return inspect_ascii_ply(path, vertex_count, properties, header_bytes)
    if file_format in {"binary_little_endian", "binary_big_endian"}:
        return inspect_binary_ply(path, file_format, vertex_count, properties, header_bytes)
    return {"path": str(path), "finite": False, "reason": f"unsupported-format:{file_format}"}


def main():
    if len(sys.argv) != 2:
        usage()
        return 1

    prefix = Path(sys.argv[1])
    if prefix.is_file():
        candidates = [prefix]
    else:
        candidates = [Path(path) for path in sorted(glob.glob(f"{prefix}*.ply"))]

    if not candidates:
        print(f"No checkpoint PLY files found for prefix: {prefix}", file=sys.stderr)
        return 1

    reports = [inspect_ply(path) for path in candidates]
    finite = [report for report in reports if report["finite"]]
    best = max(finite, key=lambda item: (item["iteration"], item["vertices"])) if finite else None
    result = {"best": best, "checkpoints": reports}
    print(json.dumps(result, indent=2))
    return 0 if best else 2


if __name__ == "__main__":
    raise SystemExit(main())
