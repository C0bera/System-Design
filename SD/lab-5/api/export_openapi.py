"""Generate openapi.yaml from the FastAPI source. Run: uv run python export_openapi.py"""

from pathlib import Path

import yaml

from app.main import app

out = Path(__file__).parent / "openapi.yaml"
out.write_text(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True, width=120))
print(f"wrote {out.name}")
