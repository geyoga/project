import json
import sys
from pathlib import Path

BASE_DIR = Path("/workspace/apartment-agent")
sys.path.insert(0, str(BASE_DIR))

from crawlers.ur import fetch_area, extract_properties


response = fetch_area("113")

properties = extract_properties(response)

for property_data in properties:
    if str(property_data.get("danchi")) != "203":
        continue

    print("=== PROPERTY ===")
    print(
        json.dumps(
            property_data,
            ensure_ascii=False,
            indent=2,
        )
    )

    break
