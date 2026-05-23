#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path


MODEL_ID = os.environ.get("SAM_MASK_MODEL", "facebook/sam-vit-base")


def usage():
    print("Usage: scripts/sam_auto_masks.py [--check] <capture> [max-frames] [label]", file=sys.stderr)


def import_status():
    status = {
        "python": sys.executable,
        "model": MODEL_ID,
        "transformers": False,
        "torch": False,
        "pillow": False,
        "ready": False,
        "downloadPolicy": "disabled unless SPLAT_SAM_ALLOW_DOWNLOAD=1",
    }
    try:
        import torch  # noqa: F401

        status["torch"] = True
    except Exception as exc:
        status["torchError"] = str(exc)
    try:
        from PIL import Image  # noqa: F401

        status["pillow"] = True
    except Exception as exc:
        status["pillowError"] = str(exc)
    try:
        from transformers import SamModel, SamProcessor  # noqa: F401

        status["transformers"] = True
    except Exception as exc:
        status["transformersError"] = str(exc)
    status["ready"] = status["torch"] and status["pillow"] and status["transformers"]
    return status


def load_manifest(capture):
    path = Path("captures") / capture / "sam_representative_frames" / "manifest.json"
    if not path.exists():
        raise ValueError(f"Missing representative frame manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def selected_frames(capture, max_frames):
    manifest = load_manifest(capture)
    frames = manifest.get("frames", [])
    if max_frames and len(frames) > max_frames:
        if max_frames == 1:
            frames = [frames[len(frames) // 2]]
        else:
            frames = [frames[round(index * (len(frames) - 1) / (max_frames - 1))] for index in range(max_frames)]
    return frames


def device_for(torch):
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def center_box(width, height):
    margin_x = round(width * 0.16)
    margin_y = round(height * 0.12)
    return [margin_x, margin_y, width - margin_x, height - margin_y]


def mask_coverage(mask_image):
    width, height = mask_image.size
    pixels = mask_image.get_flattened_data() if hasattr(mask_image, "get_flattened_data") else mask_image.getdata()
    return sum(1 for value in pixels if value > 127) / (width * height)


def generate_masks(capture, max_frames=24, label="object"):
    status = import_status()
    if not status["ready"]:
        return {"mode": "sam-auto-masks", "capture": capture, "status": "missing runtime", "environment": status}

    import torch
    from PIL import Image
    from transformers import SamModel, SamProcessor

    local_only = os.environ.get("SPLAT_SAM_ALLOW_DOWNLOAD", "0") != "1"
    try:
        processor = SamProcessor.from_pretrained(MODEL_ID, local_files_only=local_only)
        model = SamModel.from_pretrained(MODEL_ID, local_files_only=local_only)
    except Exception as exc:
        return {
            "mode": "sam-auto-masks",
            "capture": capture,
            "status": "missing model",
            "model": MODEL_ID,
            "error": str(exc),
            "next": "Run with SPLAT_SAM_ALLOW_DOWNLOAD=1 to let transformers download the SAM checkpoint, or pre-cache SAM_MASK_MODEL locally.",
            "environment": status,
        }

    device = device_for(torch)
    model.to(device)
    model.eval()

    capture_dir = Path("captures") / capture
    output_dir = capture_dir / "sam_masks" / label
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []

    for frame in selected_frames(capture, max_frames):
        image_path = Path(frame["output"])
        if not image_path.exists():
            image_path = capture_dir / "images" / frame["frame"]
        if not image_path.exists():
            continue

        image = Image.open(image_path).convert("RGB")
        box = center_box(*image.size)
        inputs = processor(image, input_boxes=[[box]], return_tensors="pt")
        inputs = {
            key: value.to(dtype=torch.float32, device=device) if torch.is_floating_point(value) else value.to(device)
            for key, value in inputs.items()
        }
        with torch.no_grad():
            outputs = model(**inputs)
        masks = processor.image_processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu(),
        )[0]
        scores = outputs.iou_scores.detach().cpu()[0, 0]
        best_index = int(torch.argmax(scores).item())
        mask = masks[0, best_index].to(torch.uint8).numpy() * 255
        output_path = output_dir / f"{Path(frame['frame']).stem}.png"
        mask_image = Image.fromarray(mask, mode="L")
        mask_image.save(output_path)
        rows.append(
            {
                "frame": frame["frame"],
                "mask": str(output_path),
                "coverage": mask_coverage(mask_image),
                "score": float(scores[best_index].item()),
                "prompt": {"box": box},
            }
        )

    report = {
        "mode": "sam-auto-masks",
        "capture": capture,
        "status": "generated" if rows else "no frames",
        "method": "transformers-sam-box-prompt",
        "model": MODEL_ID,
        "device": device,
        "label": label,
        "frames": len(rows),
        "maskDir": str(output_dir),
        "masks": rows,
    }
    (capture_dir / "sam_masks" / f"{label}-manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def check():
    status = import_status()
    return {
        "mode": "sam-auto-masks-check",
        "ready": status["ready"],
        "environment": status,
        "next": "Use SPLAT_SAM_ALLOW_DOWNLOAD=1 bin/splatter sam-auto-masks <capture> to download/run the configured model.",
    }


def main():
    args = sys.argv[1:]
    if args == ["--check"]:
        print(json.dumps(check(), indent=2))
        return 0
    if len(args) not in (1, 2, 3):
        usage()
        return 1
    capture = args[0]
    max_frames = int(args[1]) if len(args) >= 2 else 24
    label = args[2] if len(args) == 3 else "object"
    if max_frames <= 0:
        print("max-frames must be positive", file=sys.stderr)
        return 1
    print(json.dumps(generate_masks(capture, max_frames, label), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
