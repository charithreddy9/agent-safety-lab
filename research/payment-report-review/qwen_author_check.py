"""Qwen author-only follow-up. Run from the original pilot directory."""
import json
from pathlib import Path
from run_pilot import inventory
from study import AUTHOR, post


def main():
    model = "qwen3:4b"
    baseline = json.loads(Path("payment-trials/environment.json").read_text(encoding="utf8"))
    installed = {m["name"]: m["digest"] for m in inventory("tags")["models"]}
    if installed.get(model) != baseline["models"][model] or inventory("version") != baseline["ollama"]:
        raise SystemExit("Model or Ollama version differs from the original run.")
    folder = Path("qwen-author-followup")
    folder.mkdir(exist_ok=True)
    for seed in range(1, 5):
        path = folder / f"seed{seed}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf8"))
        else:
            request = dict(model=model, messages=[dict(role="user", content=AUTHOR)],
                           stream=False, format="json", think=False,
                           options=dict(seed=seed, temperature=0.3, num_predict=1200))
            print(f"Running Qwen author follow-up, seed {seed}", flush=True)
            response = post("chat", request)
            record = dict(digest=installed[model], request=request, response=response)
            with path.open("x", encoding="utf8") as handle:
                json.dump(record, handle)
        response = record["response"]
        reply = response["message"]["content"]
        try:
            data = json.loads(reply)
            has_sql = isinstance(data, dict) and isinstance(data.get("sql"), str) and bool(data["sql"].strip())
        except ValueError:
            has_sql = False
        print(f"seed={seed} stop={response.get('done_reason')} chars={len(reply)} SQL_field={has_sql}", flush=True)


if __name__ == "__main__":
    main()
