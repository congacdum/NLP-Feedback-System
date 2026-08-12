"""Submit deterministic feedback scenarios to a running local application."""
from __future__ import annotations

import argparse
import http.cookiejar
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS = ROOT / "tests" / "fixtures" / "feedback_response_scenarios.json"


def request_json(opener, url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with opener.open(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def login(opener, base_url: str, email: str, password: str) -> None:
    request = Request(
        f"{base_url}/auth/login",
        data=urlencode({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with opener.open(request, timeout=30):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8005")
    parser.add_argument("--product-id", type=int, default=3000)
    parser.add_argument("--email", default="customer@example.com")
    parser.add_argument("--password", default="customer123")
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    args = parser.parse_args()

    scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
    cookies = http.cookiejar.CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    base_url = args.base_url.rstrip("/")
    login(opener, base_url, args.email, args.password)

    for scenario in scenarios:
        result = request_json(
            opener,
            f"{base_url}/api/feedback",
            {
                "product_id": args.product_id,
                "rating": scenario["rating"],
                "text": scenario["text"],
            },
        )
        print(json.dumps({"scenario": scenario["id"], **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
