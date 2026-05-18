#!/usr/bin/env python3
import json
import sys
from pathlib import Path

from ply_metrics import SCALAR_FORMATS, DisjointSet, _header_and_body, _parse_header, _read_scalar, mesh_metrics


def usage():
    print("Usage: scripts/mesh_largest_component.py <input.ply> <output.ply>", file=sys.stderr)


def _skip_record(data, offset, properties):
    for prop in properties:
        if prop["kind"] == "list":
            count, offset = _read_scalar(data, offset, prop["count_type"])
            offset += count * SCALAR_FORMATS[prop["item_type"]][1]
        else:
            offset += SCALAR_FORMATS[prop["type"]][1]
    return offset


def _read_face_record(data, offset, properties):
    start = offset
    indices = []
    for prop in properties:
        if prop["kind"] == "list":
            count, offset = _read_scalar(data, offset, prop["count_type"])
            values = []
            for _ in range(count):
                value, offset = _read_scalar(data, offset, prop["item_type"])
                values.append(value)
            if prop["name"] == "vertex_indices":
                indices = [int(value) for value in values]
        else:
            _, offset = _read_scalar(data, offset, prop["type"])
    return {"raw": data[start:offset], "indices": indices}, offset


def _rewrite_face_count(header, face_count):
    lines = []
    for line in header.splitlines():
        if line.startswith("element face "):
            lines.append(f"element face {face_count}")
        else:
            lines.append(line)
    return "\n".join(lines).encode("ascii") + b"\n"


def extract_largest_component(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    data = input_path.read_bytes()
    header, offset = _header_and_body(data)
    parsed = _parse_header(header)
    if parsed["format"] != "binary_little_endian":
        raise ValueError(f"Unsupported PLY format: {parsed['format']}")

    body_chunks_before_faces = []
    body_chunks_after_faces = []
    faces = []
    vertex_count = 0
    seen_faces = False

    for element in parsed["elements"]:
        start = offset
        if element["name"] == "vertex":
            vertex_count = element["count"]
            for _ in range(element["count"]):
                offset = _skip_record(data, offset, element["properties"])
            (body_chunks_after_faces if seen_faces else body_chunks_before_faces).append(data[start:offset])
        elif element["name"] == "face":
            seen_faces = True
            for _ in range(element["count"]):
                face, offset = _read_face_record(data, offset, element["properties"])
                if len(face["indices"]) >= 3:
                    faces.append(face)
        else:
            for _ in range(element["count"]):
                offset = _skip_record(data, offset, element["properties"])
            (body_chunks_after_faces if seen_faces else body_chunks_before_faces).append(data[start:offset])

    if not faces or vertex_count <= 0:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(data)
        return {"inputFaces": len(faces), "outputFaces": len(faces), "componentCount": 0, "largestComponentRatio": 1.0}

    dsu = DisjointSet(vertex_count)
    for face in faces:
        first = face["indices"][0]
        for index in face["indices"][1:]:
            if 0 <= first < vertex_count and 0 <= index < vertex_count:
                dsu.union(first, index)

    components = {}
    for face_index, face in enumerate(faces):
        roots = [dsu.find(index) for index in face["indices"] if 0 <= index < vertex_count]
        if not roots:
            continue
        root = roots[0]
        entry = components.setdefault(root, {"faces": [], "vertices": set()})
        entry["faces"].append(face_index)
        entry["vertices"].update(face["indices"])

    if not components:
        selected = faces
        component_count = 0
        largest_ratio = 1.0
    else:
        largest = max(components.values(), key=lambda item: (len(item["faces"]), len(item["vertices"])))
        selected = [faces[index] for index in largest["faces"]]
        used_vertices = {index for face in faces for index in face["indices"]}
        largest_ratio = len(largest["vertices"]) / len(used_vertices) if used_vertices else 1.0
        component_count = len(components)

    next_header = _rewrite_face_count(header, len(selected))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        next_header
        + b"".join(body_chunks_before_faces)
        + b"".join(face["raw"] for face in selected)
        + b"".join(body_chunks_after_faces)
    )
    return {
        "inputFaces": len(faces),
        "outputFaces": len(selected),
        "componentCount": component_count,
        "largestComponentRatio": largest_ratio,
        "metrics": mesh_metrics(output_path),
    }


def main():
    if len(sys.argv) != 3:
        usage()
        return 1
    report = extract_largest_component(sys.argv[1], sys.argv[2])
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
