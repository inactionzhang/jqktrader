# jqktrader HTTP Service

项目总说明见 [README.md](/c:/ai/jqktrader/README.md:1)。这里保留 HTTP 服务的最小使用说明。

## Start

```bash
python http_service.py --host 0.0.0.0 --port 8000
```

Default paths used by the HTTP service:

- `exe_path = C:\thshrj\thsh\xiadan.exe`
- `tesseract_cmd = C:\Program Files\Tesseract-OCR\tesseract.exe`

Startup with automatic connection:

```bash
python http_service.py --host 0.0.0.0 --port 8000 --auto-connect
```

If you want the service to start first and connect only before the first business call:

```bash
python http_service.py --host 0.0.0.0 --port 8000 --connect-on-first-use
```

## Main routes

- `GET /health`
- `GET /interfaces`
- `GET|POST /trader/<name>`
- `GET /objects/<handle>`
- `GET|POST /objects/<handle>/<name>`

## Examples

Read balance:

```bash
curl http://127.0.0.1:8000/trader/balance
```

Buy stock:

```bash
curl -X POST http://127.0.0.1:8000/trader/buy ^
  -H "Content-Type: application/json" ^
  -d "{\"security\":\"600000\",\"price\":10.5,\"amount\":100}"
```

You can still call `/trader/connect` manually, but when `--auto-connect` or `--connect-on-first-use` is enabled, it is no longer required.

The root route `/` also returns the current interface list and example payloads.
