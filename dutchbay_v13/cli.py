import argparse
import yaml
from dutchbay_v13.adapters import run_irr_demo

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=str, required=True)
    parser.add_argument('--mode', type=str, required=True)
    args = parser.parse_args()

    with open(args.config, 'r') as f:
        cfg = yaml.safe_load(f)

    if args.mode == "irr":
        print("Dispatching mode irr -> dutchbay_v13.adapters::run_irr_demo")
        run_irr_demo(cfg)
    else:
        print(f"Unknown mode: {args.mode}")

if __name__ == "__main__":
    main()
