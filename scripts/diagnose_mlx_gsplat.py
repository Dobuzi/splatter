#!/usr/bin/env python3
import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np


def load_trainer(repo_dir):
    repo = Path(repo_dir)
    sys.path.insert(0, str(repo / "src"))
    trainer_path = repo / "examples" / "simple_trainer.py"
    spec = importlib.util.spec_from_file_location("gsplat_mlx_simple_trainer", trainer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {trainer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def finite_stats(name, value):
    array = np.array(value)
    finite = np.isfinite(array)
    total = array.size
    finite_count = int(finite.sum())
    if finite_count:
        finite_values = array[finite]
        min_value = float(finite_values.min())
        max_value = float(finite_values.max())
        mean_abs = float(np.abs(finite_values).mean())
    else:
        min_value = max_value = mean_abs = math.nan
    print(
        f"- {name}: finite {finite_count}/{total}, "
        f"nan {int(np.isnan(array).sum())}, inf {int(np.isinf(array).sum())}, "
        f"min {min_value:.6g}, max {max_value:.6g}, mean_abs {mean_abs:.6g}"
    )
    return finite_count == total


def main():
    parser = argparse.ArgumentParser(description="Diagnose gsplat-mlx simple trainer NaN sources.")
    parser.add_argument("--repo", default=".local/gsplat-mlx")
    parser.add_argument("--num-gaussians", type=int, default=20)
    parser.add_argument("--width", type=int, default=16)
    parser.add_argument("--height", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-5)
    args = parser.parse_args()

    trainer = load_trainer(args.repo)
    import mlx.core as mx

    params = trainer.create_random_gaussians(args.num_gaussians)
    target = trainer.create_target_image(args.width, args.height)
    k_matrix, viewmat = trainer.create_camera(args.width, args.height)
    param_names = ["means", "quats", "scales", "opacities", "sh_coeffs"]

    def loss_fn(means, quats, scales, opacities, sh_coeffs):
        rendered = trainer._differentiable_render(
            means=means,
            quats=quats,
            scales_exp=mx.exp(scales),
            opacities_sig=mx.sigmoid(opacities),
            sh_coeffs=sh_coeffs,
            viewmat=viewmat,
            K=k_matrix,
            width=args.width,
            height=args.height,
        )
        return trainer._l1_loss(rendered, target)

    print(f"mlx device: {mx.default_device()}")
    loss, grads = mx.value_and_grad(loss_fn, argnums=(0, 1, 2, 3, 4))(
        params["means"],
        params["quats"],
        params["scales"],
        params["opacities"],
        params["sh_coeffs"],
    )
    mx.eval(loss, *grads)
    print(f"initial_loss: {float(loss.item()):.6f}")

    all_grad_finite = True
    for name, grad in zip(param_names, grads):
        all_grad_finite = finite_stats(f"grad.{name}", grad) and all_grad_finite

    repeat_loss = loss_fn(
        params["means"],
        params["quats"],
        params["scales"],
        params["opacities"],
        params["sh_coeffs"],
    )
    mx.eval(repeat_loss)
    print(f"repeat_loss_without_update: {float(repeat_loss.item()):.6f}")

    beta1, beta2, eps = 0.9, 0.999, 1e-8
    param_lrs = {
        "means": args.lr,
        "quats": args.lr * 0.1,
        "scales": args.lr * 0.5,
        "opacities": args.lr * 0.5,
        "sh_coeffs": args.lr * 0.5,
    }

    updated = {}
    for name, grad in zip(param_names, grads):
        m_hat = (1 - beta1) * grad / (1 - beta1)
        v_hat = (1 - beta2) * grad * grad / (1 - beta2)
        updated[name] = params[name] - param_lrs[name] * m_hat / (mx.sqrt(v_hat) + eps)

    mx.eval(*updated.values())
    all_param_finite = True
    for name in param_names:
        all_param_finite = finite_stats(f"updated.{name}", updated[name]) and all_param_finite

    next_loss = loss_fn(
        updated["means"],
        updated["quats"],
        updated["scales"],
        updated["opacities"],
        updated["sh_coeffs"],
    )
    mx.eval(next_loss)
    print(f"loss_after_one_adam_step: {float(next_loss.item()):.6f}")

    initial_loss = float(loss.item())
    repeated_loss = float(repeat_loss.item())

    if not all_grad_finite:
        print("diagnosis: non-finite gradient before optimizer update")
        return 2
    if abs(repeated_loss - initial_loss) > 1e-5:
        print("diagnosis: differentiable render is not repeatable before any optimizer update")
        return 5
    if not all_param_finite:
        print("diagnosis: optimizer update creates non-finite parameters")
        return 3
    if not math.isfinite(float(next_loss.item())):
        print("diagnosis: finite first update leads to non-finite forward pass")
        return 4
    print("diagnosis: first update is finite")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
