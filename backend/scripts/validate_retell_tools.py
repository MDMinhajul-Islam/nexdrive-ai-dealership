"""Validate Retell definitions against FastAPI OpenAPI."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"backend"))
from app.main import app
def main():
 config=json.loads((ROOT/"retell"/"tools.json").read_text(encoding="utf-8")); paths=app.openapi()["paths"]; errors=[]
 for tool in config["tools"]:
  if tool["path"] not in paths or tool["method"].lower() not in paths.get(tool["path"],{}): errors.append(tool["name"])
 print(f"PASS: {len(config['tools'])} Retell tools" if not errors else f"FAIL: missing contracts {errors}"); return bool(errors)
if __name__=="__main__": raise SystemExit(main())
