"""Container readiness probe using the configured institution host, not the public schema."""

import json
import os
import sys
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def main():
    variant = os.environ["SIS_VARIANT"]
    public_url = urlparse(os.environ[f"SIS_{variant.upper()}_API_URL"])
    if not public_url.hostname:
        raise ValueError("The institution API URL must contain a hostname.")
    request = Request(
        "http://127.0.0.1:8000/ready/",
        headers={"Host": public_url.netloc, "X-Forwarded-Proto": public_url.scheme},
    )
    with urlopen(request, timeout=5) as response:
        payload = json.load(response)
    if payload.get("status") != "ready":
        raise ValueError("Institution dependencies are not ready.")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, URLError) as exc:
        sys.exit(f"Readiness failed: {exc}")
