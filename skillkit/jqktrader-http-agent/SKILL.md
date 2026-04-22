---
name: jqktrader-http-agent
description: 通过本仓库里的 jqktrader HTTP 服务查询账户数据和执行交易动作。用于模型需要通过本地 HTTP API 调用余额、持仓、当日委托、买入、卖出、撤单、打新等能力时。
---

# jqktrader HTTP 调用技能

使用这个技能时，优先复用本目录下的 Python 脚本来调用 HTTP 服务，而不是临时拼接请求代码。

## 默认约定

- 默认服务地址：`http://127.0.0.1:8000`
- 查询型接口优先用 `GET /trader/<name>`
- 动作型接口优先用 `POST /trader/<name>`
- 如果不确定服务是否在线，先执行健康检查脚本
- 如果不确定某个 trader 能力是否暴露，先执行接口列表脚本

## 优先使用的脚本

### `scripts/check_service.py`

用途：

- 检查服务是否可达
- 调用 `/health`

示例：

```bash
python skillkit/jqktrader-http-agent/scripts/check_service.py
python skillkit/jqktrader-http-agent/scripts/check_service.py --base-url http://127.0.0.1:8000
```

### `scripts/list_interfaces.py`

用途：

- 查询 `/interfaces`
- 查看当前 HTTP 服务暴露了哪些 trader 接口

示例：

```bash
python skillkit/jqktrader-http-agent/scripts/list_interfaces.py
python skillkit/jqktrader-http-agent/scripts/list_interfaces.py --base-url http://127.0.0.1:8000
```

### `scripts/invoke_trader.py`

用途：

- 统一调用 `/trader/<name>`
- 支持 `GET` 和 `POST`
- `POST` 时通过 JSON 请求体传参

示例：

查询余额：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py balance
```

查询持仓：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py position
```

买入：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py buy --method POST --data "{\"security\":\"600000\",\"price\":10.5,\"amount\":100}"
```

卖出：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py sell --method POST --data "{\"security\":\"600000\",\"price\":10.8,\"amount\":100}"
```

撤单：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py cancel_entrust --method POST --data "{\"entrust_no\":\"合同编号\"}"
```

自动打新：

```bash
python skillkit/jqktrader-http-agent/scripts/invoke_trader.py auto_ipo --method POST
```

## 推荐调用顺序

1. 先执行 `check_service.py`
2. 如需探测能力，执行 `list_interfaces.py`
3. 明确接口名后，用 `invoke_trader.py` 发起调用
4. 如果用户只要脚本，直接给出可运行命令，不要再重复手写 HTTP 请求代码

## 额外说明

- 如果服务默认启用了自动连接，不要默认额外调用 `/trader/connect`
- 如果后续需要支持 `/objects/<handle>`，再补专门脚本
- 只有在需要核对行为时，才去读 `http_service.py`、`README.md`、`README_HTTP_SERVICE.md`
