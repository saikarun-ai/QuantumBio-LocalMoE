#!/usr/bin/env python3
import argparse
import os
import shutil
import sys


def detect_source() -> str:
    candidates = [
        os.environ.get("MODEL_EXTRA_DIRECTORIES", ""),
        os.environ.get("MODEL_SOURCE"),
        r"D:\Gen AI Applications\LLMS",
    ]
    for candidate in candidates:
        for entry in (candidate.split(",") if candidate else []):
            entry = entry.strip()
            if entry and os.path.isdir(entry):
                return entry
    return ""


def list_models(target: str = "./models") -> None:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from quantumbio_moe.inference.registry import ModelRegistry

    registry = ModelRegistry()
    print("Detected model directory:", target)
    print("  text models:")
    for model in registry.text_models:
        print(f"    {model.name} ({model.size_bytes / 1e6:.0f} MB)")
    print("  diffusion models:")
    for model in registry.diffusion_models:
        print(f"    {model.name} ({model.size_bytes / 1e6:.0f} MB)")
    print("  audio models:")
    for model in registry.audio_models:
        print(f"    {model.name} ({model.size_bytes / 1e6:.0f} MB)")


def export(source: str, dest: str, hardlink: bool) -> int:
    os.makedirs(dest, exist_ok=True)
    copied = 0
    for filename in os.listdir(source):
        path = os.path.join(source, filename)
        if not os.path.isfile(path) or not filename.lower().endswith(".gguf"):
            continue
        target = os.path.join(dest, filename)
        if os.path.exists(target):
            continue
        if hardlink:
            os.link(path, target)
        else:
            shutil.copy2(path, target)
        copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage local GGUF model weights for QuantumBio-LocalMoE.")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List models discovered by the registry")
    list_parser.add_argument("--dir", default="./models")

    export_parser = sub.add_parser("export", help="Copy or hardlink GGUF weights into the models directory")
    export_parser.add_argument("--source", default="")
    export_parser.add_argument("--dest", default="./models")
    export_parser.add_argument("--hardlink", action="store_true", help="Create hardlinks instead of copying")

    args = parser.parse_args()
    if args.command == "list":
        list_models(args.dir)
    elif args.command == "export":
        source = args.source or detect_source()
        if not source or not os.path.isdir(source):
            print("No source model directory found. Pass --source <folder with .gguf files>.")
            sys.exit(1)
        copied = export(source, args.dest, args.hardlink)
        print(f"Exported {copied} model file(s) to {args.dest}")


if __name__ == "__main__":
    main()