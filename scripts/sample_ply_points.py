#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

from ply_metrics import SCALAR_FORMATS, _header_and_body, _parse_header, _read_scalar


def usage():
    print("Usage: scripts/sample_ply_points.py <input.ply> <output.ply> [max-points]", file=sys.stderr)


def read_vertices(path, max_points):
    data = Path(path).read_bytes()
    header, offset = _header_and_body(data)
    parsed = _parse_header(header)
    if parsed["format"] != "binary_little_endian":
        raise ValueError(f"Unsupported PLY format: {parsed['format']}")

    vertex_element = next((element for element in parsed["elements"] if element["name"] == "vertex"), None)
    if not vertex_element:
        return []

    stride = max(1, math.ceil(vertex_element["count"] / max_points))
    vertices = []
    vertex_index = 0

    for element in parsed["elements"]:
        for _ in range(element["count"]):
            keep_vertex = element["name"] == "vertex" and vertex_index % stride == 0 and len(vertices) < max_points
            vertex = {"x": 0.0, "y": 0.0, "z": 0.0, "red": 210, "green": 218, "blue": 230}

            for prop in element["properties"]:
                if prop["kind"] == "list":
                    count, offset = _read_scalar(data, offset, prop["count_type"])
                    offset += count * SCALAR_FORMATS[prop["item_type"]][1]
                    continue

                value, offset = _read_scalar(data, offset, prop["type"])
                if keep_vertex and prop["name"] in vertex:
                    vertex[prop["name"]] = value

            if element["name"] == "vertex":
                if keep_vertex:
                    vertices.append(
                        (
                            float(vertex["x"]),
                            float(vertex["y"]),
                            float(vertex["z"]),
                            int(vertex["red"]),
                            int(vertex["green"]),
                            int(vertex["blue"]),
                        )
                    )
                vertex_index += 1

    return vertices


def write_point_cloud(path, vertices):
    header = f"""ply
format binary_little_endian 1.0
element vertex {len(vertices)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
end_header
"""
    with Path(path).open("wb") as handle:
        handle.write(header.encode("ascii"))
        for vertex in vertices:
            handle.write(struct.pack("<fffBBB", *vertex))


def sample_point_cloud(input_path, output_path, max_points=200000):
    vertices = read_vertices(input_path, max_points)
    if not vertices:
        raise ValueError(f"No vertices found in {input_path}")
    write_point_cloud(output_path, vertices)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "points": len(vertices),
        "maxPoints": max_points,
    }


def main():
    if len(sys.argv) not in (3, 4):
        usage()
        return 1
    max_points = int(sys.argv[3]) if len(sys.argv) == 4 else 200000
    report = sample_point_cloud(Path(sys.argv[1]), Path(sys.argv[2]), max_points)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
