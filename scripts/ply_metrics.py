#!/usr/bin/env python3
import json
import math
import struct
import sys
from pathlib import Path


SCALAR_FORMATS = {
    "char": ("b", 1),
    "int8": ("b", 1),
    "uchar": ("B", 1),
    "uint8": ("B", 1),
    "short": ("h", 2),
    "int16": ("h", 2),
    "ushort": ("H", 2),
    "uint16": ("H", 2),
    "int": ("i", 4),
    "int32": ("i", 4),
    "uint": ("I", 4),
    "uint32": ("I", 4),
    "float": ("f", 4),
    "float32": ("f", 4),
    "double": ("d", 8),
    "float64": ("d", 8),
}


def _read_scalar(data, offset, scalar_type):
    fmt, size = SCALAR_FORMATS[scalar_type]
    return struct.unpack_from("<" + fmt, data, offset)[0], offset + size


def _header_and_body(data):
    marker = b"end_header"
    index = data.find(marker)
    if index < 0:
        raise ValueError("Invalid PLY: missing end_header")
    offset = index + len(marker)
    if offset < len(data) and data[offset] == 13:
        offset += 1
    if offset < len(data) and data[offset] == 10:
        offset += 1
    return data[:offset].decode("ascii", errors="ignore"), offset


def _parse_header(header):
    elements = []
    current = None
    ply_format = None
    comments = []
    for line in header.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "format":
            ply_format = parts[1]
        elif parts[0] == "comment":
            comments.append(" ".join(parts[1:]))
        elif parts[0] == "element":
            current = {"name": parts[1], "count": int(parts[2]), "properties": []}
            elements.append(current)
        elif parts[0] == "property" and current:
            if parts[1] == "list":
                current["properties"].append(
                    {
                        "kind": "list",
                        "count_type": parts[2],
                        "item_type": parts[3],
                        "name": parts[4],
                    }
                )
            else:
                current["properties"].append({"kind": "scalar", "type": parts[1], "name": parts[2]})
    return {"format": ply_format, "elements": elements, "comments": comments}


def read_ply(path):
    data = Path(path).read_bytes()
    header, offset = _header_and_body(data)
    parsed = _parse_header(header)
    if parsed["format"] != "binary_little_endian":
        raise ValueError(f"Unsupported PLY format: {parsed['format']}")

    vertices = []
    faces = []
    has_texcoords = False

    for element in parsed["elements"]:
        for _ in range(element["count"]):
            if element["name"] == "vertex":
                vertex = {"x": 0.0, "y": 0.0, "z": 0.0}
                for prop in element["properties"]:
                    if prop["kind"] == "list":
                        count, offset = _read_scalar(data, offset, prop["count_type"])
                        offset += count * SCALAR_FORMATS[prop["item_type"]][1]
                    else:
                        value, offset = _read_scalar(data, offset, prop["type"])
                        if prop["name"] in vertex:
                            vertex[prop["name"]] = float(value)
                vertices.append((vertex["x"], vertex["y"], vertex["z"]))
            elif element["name"] == "face":
                face = []
                for prop in element["properties"]:
                    if prop["kind"] == "list":
                        count, offset = _read_scalar(data, offset, prop["count_type"])
                        values = []
                        for _ in range(count):
                            value, offset = _read_scalar(data, offset, prop["item_type"])
                            values.append(value)
                        if prop["name"] == "vertex_indices":
                            face = [int(value) for value in values]
                        elif prop["name"] == "texcoord":
                            has_texcoords = has_texcoords or bool(values)
                    else:
                        _, offset = _read_scalar(data, offset, prop["type"])
                if len(face) >= 3:
                    faces.append(face)
            else:
                for prop in element["properties"]:
                    if prop["kind"] == "list":
                        count, offset = _read_scalar(data, offset, prop["count_type"])
                        offset += count * SCALAR_FORMATS[prop["item_type"]][1]
                    else:
                        offset += SCALAR_FORMATS[prop["type"]][1]

    texture_files = [
        comment.split("TextureFile ", 1)[1]
        for comment in parsed["comments"]
        if comment.startswith("TextureFile ")
    ]
    return {
        "vertices": vertices,
        "faces": faces,
        "hasTexcoords": has_texcoords,
        "textureFiles": texture_files,
    }


class DisjointSet:
    def __init__(self, size):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value):
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left, right):
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            self.parent[left_root] = right_root
        elif self.rank[left_root] > self.rank[right_root]:
            self.parent[right_root] = left_root
        else:
            self.parent[right_root] = left_root
            self.rank[left_root] += 1


def _triangle_area(a, b, c):
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)


def mesh_metrics(path):
    ply = read_ply(path)
    vertices = ply["vertices"]
    faces = ply["faces"]
    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    bbox_min = [min(xs), min(ys), min(zs)] if vertices else [0, 0, 0]
    bbox_max = [max(xs), max(ys), max(zs)] if vertices else [0, 0, 0]
    bbox_size = [bbox_max[index] - bbox_min[index] for index in range(3)]
    center = [(bbox_min[index] + bbox_max[index]) / 2 for index in range(3)]
    diagonal = math.sqrt(sum(value * value for value in bbox_size))
    volume = bbox_size[0] * bbox_size[1] * bbox_size[2]

    dsu = DisjointSet(len(vertices))
    degenerate = 0
    total_area = 0.0
    for face in faces:
        first = face[0]
        for index in face[1:]:
            dsu.union(first, index)
        for i in range(1, len(face) - 1):
            area = _triangle_area(vertices[face[0]], vertices[face[i]], vertices[face[i + 1]])
            total_area += area
            if area <= 1e-10:
                degenerate += 1

    used_vertices = {index for face in faces for index in face}
    components = {}
    for index in used_vertices:
        root = dsu.find(index)
        components[root] = components.get(root, 0) + 1
    component_sizes = sorted(components.values(), reverse=True)
    largest = component_sizes[0] if component_sizes else 0

    return {
        "vertices": len(vertices),
        "faces": len(faces),
        "bbox": {"min": bbox_min, "max": bbox_max, "size": bbox_size, "center": center, "diagonal": diagonal, "volume": volume},
        "surfaceArea": total_area,
        "faceDensity": len(faces) / volume if volume > 0 else 0,
        "componentCount": len(component_sizes),
        "largestComponentVertices": largest,
        "largestComponentRatio": largest / len(used_vertices) if used_vertices else 0,
        "degenerateFaces": degenerate,
        "degenerateFaceRatio": degenerate / len(faces) if faces else 0,
        "hasTexcoords": ply["hasTexcoords"],
        "textureFiles": ply["textureFiles"],
    }


def camera_for_metrics(metrics):
    center = metrics["bbox"]["center"]
    diagonal = max(metrics["bbox"]["diagonal"], 1.0)
    distance = diagonal * 1.35
    return {
        "target": [round(value, 4) for value in center],
        "position": [round(center[0], 4), round(center[1], 4), round(center[2] + distance, 4)],
        "distance": round(distance, 4),
        "minDistance": round(max(diagonal * 0.02, 0.05), 4),
        "maxDistance": round(max(diagonal * 8.0, distance * 2.0), 4),
    }


def public_metrics(metrics):
    return {
        "vertices": metrics["vertices"],
        "faces": metrics["faces"],
        "bbox": metrics["bbox"],
        "surfaceArea": metrics["surfaceArea"],
        "faceDensity": metrics["faceDensity"],
        "componentCount": metrics["componentCount"],
        "largestComponentRatio": metrics["largestComponentRatio"],
        "degenerateFaceRatio": metrics["degenerateFaceRatio"],
        "hasTexcoords": metrics["hasTexcoords"],
        "textureFiles": metrics["textureFiles"],
    }


def main():
    if len(sys.argv) != 2:
        print("Usage: scripts/ply_metrics.py <mesh.ply>", file=sys.stderr)
        return 1
    print(json.dumps(mesh_metrics(sys.argv[1]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
