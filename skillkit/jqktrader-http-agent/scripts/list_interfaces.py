import argparse
import json
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="List jqktrader HTTP interfaces")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    url = args.base_url.rstrip("/") + "/interfaces"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
