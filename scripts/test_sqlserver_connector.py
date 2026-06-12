import json
import os
import sys

import httpx


def main() -> None:
    url = os.environ.get("REPORT_CONNECTOR_URL", "http://127.0.0.1:8090").rstrip("/")
    secret = os.environ.get("REPORT_CONNECTOR_SECRET") or os.environ.get("CONNECTOR_SECRET", "")
    tenant_id = os.environ.get("REPORT_TENANT_ID", "")
    if not secret or not tenant_id:
        raise SystemExit("Set REPORT_CONNECTOR_SECRET (or CONNECTOR_SECRET) and REPORT_TENANT_ID")
    response = httpx.post(
        f"{url}/diagnostics",
        headers={"X-Snapkey-Connector-Secret": secret},
        json={"tenant_id": tenant_id},
        timeout=15,
    )
    print(json.dumps(response.json(), indent=2))
    sys.exit(0 if response.is_success and not response.json().get("missing_views") else 1)


if __name__ == "__main__":
    main()
