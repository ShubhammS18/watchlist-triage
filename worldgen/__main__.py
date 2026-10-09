"""python -m worldgen --seed N --out DIR   (default seed from config.json, default folder data/world)"""
import argparse

from . import ROOT, load_config
from .build import BuildError, generate, write


def main(argv=None):
    config = load_config()
    parser = argparse.ArgumentParser(prog="python -m worldgen", description="Generate the synthetic watchlist world.")
    parser.add_argument("--seed", type=int, default=config["seed"], help="seed (default: config.json)")
    parser.add_argument("--out", default=str(ROOT.parent.joinpath("data", "world")), help="output folder (default: data/world)")
    args = parser.parse_args(argv)
    try:
        files, summary = generate(args.seed)
    except BuildError as error:
        raise SystemExit(f"build failed: {error}")
    write(files, args.out)
    print(f"wrote {len(files)} files to {args.out} (seed {args.seed}); {summary}")


if __name__ == "__main__":
    main()
