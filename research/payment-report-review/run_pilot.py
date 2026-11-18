"""Run the ten planned offline-model trials and summarize paired outcomes."""
import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import study

MODELS = ("qwen3:4b", "llama3.2:latest")
SEEDS = range(1, 6)

def inventory(route):
    with urlopen("http://127.0.0.1:11434/api/" + route, timeout=10) as response:
        return json.load(response)

def classify(path):
    if not path.exists():
        return "pending"
    try:
        lines = [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]
    except ValueError:
        return "incomplete"
    if any("author_error" in line for line in lines):
        return "author_error"
    arms = {line["arm"]: line["result"] for line in lines if "arm" in line}
    controls = next((line["author_controls"] for line in lines if "author_controls" in line), [])
    if not controls or arms.keys() != {"self", "independent"}:
        return "incomplete"
    if not any(c["detects_balanced_error"] for c in controls):
        return "no_eligible_fixture_error"
    detected = [name for name, result in arms.items() if result["detects_balanced_error"]]
    return {0: "neither", 2: "both"}.get(len(detected)) or detected[0] + "_only"

def paths(folder, model):
    return [(seed, folder / f"{model.replace(':', '-')}-seed{seed}.jsonl") for seed in SEEDS]

def summarize(folder):
    return {model: dict(Counter(classify(path) for _,path in paths(folder, model))) for model in MODELS}

def run(folder):
    tags = {m["name"]: m["digest"] for m in inventory("tags")["models"]}
    missing = [m for m in MODELS if m not in tags]
    if missing:
        raise SystemExit("Missing local models: " + ", ".join(missing))
    metadata = dict(models={m: tags[m] for m in MODELS}, ollama=inventory("version"),
                    python=platform.python_version(), system=platform.platform(),
                    study_sha256=hashlib.sha256(Path(study.__file__).read_bytes()).hexdigest())
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / "environment.json"
    if manifest.exists() and json.loads(manifest.read_text(encoding="utf8")) != metadata:
        raise SystemExit("Environment changed. Use a new --out directory.")
    if not manifest.exists():
        with manifest.open("x", encoding="utf8") as handle:
            json.dump(metadata, handle, indent=2)
    for model in MODELS:
        for seed,path in paths(folder, model):
            if not path.exists():
                print(f"Running {model}, seed {seed}", flush=True)
                study.trial(model, seed, path)
            elif classify(path) == "incomplete":
                print(f"Preserving interrupted trial: {path}", flush=True)
    summary = summarize(folder)
    (folder / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("payment-trials"))
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    try:
        result = summarize(args.out) if args.summary_only else run(args.out)
    except (URLError, TimeoutError) as exc:
        raise SystemExit(f"Local Ollama request failed: {exc}. Existing trials are preserved.")
    print(json.dumps(result, indent=2))
