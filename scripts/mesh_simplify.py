#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path

from ply_metrics import read_ply


def usage():
    print("Usage: scripts/mesh_simplify.py <input.ply> <output.ply> [max-faces]", file=sys.stderr)


def triangle_area(vertices, face):
    if len(face) < 3:
        return 0.0
    a, b, c = (vertices[face[0]], vertices[face[1]], vertices[face[2]])
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)


def write_mesh(path, vertices, faces):
    header = f"""ply
format binary_little_endian 1.0
element vertex {len(vertices)}
property float x
property float y
property float z
element face {len(faces)}
property list uchar int vertex_indices
end_header
"""
    with Path(path).open("wb") as handle:
        handle.write(header.encode("ascii"))
        for vertex in vertices:
            handle.write(struct.pack("<fff", vertex[0], vertex[1], vertex[2]))
        for face in faces:
            handle.write(struct.pack("<Biii", 3, face[0], face[1], face[2]))


def simplify(input_path, output_path, max_faces=50000):
    ply = read_ply(input_path)
    source_vertices = ply["vertices"]
    source_faces = [
        face[:3]
        for face in ply["faces"]
        if len(face) >= 3 and triangle_area(source_vertices, face[:3]) > 1e-10
    ]
    if len(source_faces) > max_faces:
        stride = len(source_faces) / max_faces
        source_faces = [source_faces[int(index * stride)] for index in range(max_faces)]

    used = sorted({index for face in source_faces for index in face})
    remap = {old: new for new, old in enumerate(used)}
    vertices = [source_vertices[index] for index in used]
    faces = [[remap[index] for index in face] for face in source_faces]
    write_mesh(output_path, vertices, faces)
    return {
        "input": str(input_path),
        "output": str(output_path),
        "vertices": len(vertices),
        "faces": len(faces),
        "maxFaces": max_faces,
    }


def main():
    if len(sys.argv) not in (3, 4):
        usage()
        return 1
    max_faces = int(sys.argv[3]) if len(sys.argv) == 4 else 50000
    print(json.dumps(simplify(Path(sys.argv[1]), Path(sys.argv[2]), max_faces), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
