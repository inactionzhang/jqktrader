import argparse
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke jqktrader trader HTTP endpoint")
    parser.add_argument("name", help="Trader method or property name")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--method", choices=["GET", "POST"], default="GET")
    parser.add_argument("--data", help="JSON request body for POST calls")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/trader/" + args.name
    body = None
    headers = {}

    if args.method == "POST":
        raw = args.data if args.data else "{}"
        json.loads(raw)
        body = raw.encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=args.method)
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
