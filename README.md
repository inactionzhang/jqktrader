# jqktrader

`jqktrader` 是一个基于 Windows GUI 自动化的股票交易客户端封装，当前仓库默认实现的是同花顺客户端交易对象，并额外提供了一个零第三方 Web 框架依赖的 HTTP 服务层，方便通过脚本或外部系统调用。

它适合这类场景：

- 已经安装并使用 Windows 券商/交易客户端
- 希望通过 Python 自动读取资金、持仓、当日委托、当日成交
- 希望以程序方式执行买入、卖出、撤单、逆回购、新股申购
- 希望把本地交易能力通过 HTTP 暴露给其他进程或服务调用

## 主要功能

- 连接已登录的交易客户端
- 查询账户资金信息
- 查询持仓、当日委托、当日成交
- 普通买卖
- 市价买卖
- 指定委托单撤单
- 全部撤单
- 国债正回购、逆回购
- 自动打新
- HTTP 服务封装

## 当前实现边界

- 这是一个 Windows 专用项目，依赖 `pywinauto` 控制桌面客户端
- 当前默认入口 `jqktrader.api.use()` 返回的是 `ClientTrader`，即“连接已打开客户端”的模式
- 仓库里存在 `BaseLoginClientTrader` 抽象类，但没有提供可直接使用的登录实现；也就是说，实际使用时通常是先手动登录客户端，再由程序连接
- HTTP 服务默认暴露的是 `ClientTrader` 的公开接口

## 支持的客户端配置

项目内置了多种客户端配置模板，定义在 [config/client.py](/c:/ai/jqktrader/config/client.py:1)：

- `ths`
- `yh`
- `ht`
- `gj`
- `gf`
- `wk`
- `htzq`
- `universal`

当前 `ClientTrader.broker_type` 默认返回 `ths`，也就是同花顺配置。

## 环境要求

- Windows
- Python 3.6+
- 已安装并能正常打开交易客户端
- 如果客户端查询过程中会出现验证码，建议安装 `Tesseract OCR`

## 依赖

项目已经提供了 [requirements.txt](/c:/ai/jqktrader/requirements.txt:1)，可以直接安装：

```bash
pip install -r requirements.txt
```

如果需要识别验证码，还需要额外安装 Tesseract 可执行程序，并把路径传给 `connect(..., tesseract_cmd=...)` 或 HTTP 服务启动参数 `--tesseract-cmd`。

Tesseract 参考：

- https://github.com/tesseract-ocr/tesseract/wiki

## 快速开始

### 1. 连接已登录客户端

如果你直接在源码目录使用 Python，建议从仓库的父目录执行脚本，或者把仓库父目录加入 `PYTHONPATH`，这样才能正常 `import jqktrader`。

示例：

```python
from jqktrader.api import use

trader = use(debug=True)
trader.connect(
    exe_path=r"C:\ths\xiadan.exe",
    tesseract_cmd=r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    editor_need_type_keys=True,
)

print(trader.balance)
print(trader.position)
```

### 2. 常见查询接口

```python
from jqktrader.api import use

trader = use()
trader.connect(exe_path=r"C:\ths\xiadan.exe")

print(trader.balance)
print(trader.position)
print(trader.today_entrusts)
print(trader.today_trades)
print(trader.cancel_entrusts)
```

### 3. 常见交易接口

```python
from jqktrader.api import use

trader = use()
trader.connect(exe_path=r"C:\ths\xiadan.exe")

trader.buy("600000", 10.50, 100)
trader.sell("600000", 10.80, 100)
trader.market_buy("600000", 100)
trader.market_sell("600000", 100)
trader.cancel_entrust("合同编号")
trader.cancel_all_entrusts()
trader.auto_ipo()
```

## Python API 概览

核心公开接口主要来自 [clienttrader.py](/c:/ai/jqktrader/clienttrader.py:105)：

- `connect(exe_path=None, tesseract_cmd=None, editor_need_type_keys=True, **kwargs)`
- `balance`
- `position`
- `today_entrusts`
- `today_trades`
- `cancel_entrusts`
- `cancel_entrust(entrust_no)`
- `cancel_all_entrusts()`
- `buy(security, price, amount, **kwargs)`
- `sell(security, price, amount, **kwargs)`
- `market_buy(security, amount, ttype=None, limit_price=None, **kwargs)`
- `market_sell(security, amount, ttype=None, limit_price=None, **kwargs)`
- `repo(security, price, amount, **kwargs)`
- `reverse_repo(security, price, amount, **kwargs)`
- `auto_ipo()`
- `refresh()`
- `exit()`

返回值通常是以下几类：

- 查询类接口：返回 `dict` 或 `list[dict]`
- 交易类接口：通常返回包含 `entrust_no` 或 `message` 的字典
- 异常类情况：可能抛出运行时异常，或返回错误提示

## HTTP 服务

除了 Python API，这个项目还提供了一个内置 HTTP 服务实现，代码在 [http_service.py](/c:/ai/jqktrader/http_service.py:1)。

### 启动服务

最简单的启动方式：

```bash
python http_service.py --host 0.0.0.0 --port 8000
```

HTTP 服务内置的默认连接路径是：

- `exe_path = C:\thshrj\thsh\xiadan.exe`
- `tesseract_cmd = C:\Program Files\Tesseract-OCR\tesseract.exe`

所以如果你的环境就是这两个默认路径，启动时可以不再额外传参。

推荐直接使用自动连接模式：

```bash
python http_service.py --host 0.0.0.0 --port 8000 --auto-connect
```

如果希望服务先启动，等第一次业务请求时再连接客户端：

```bash
python http_service.py --host 0.0.0.0 --port 8000 --connect-on-first-use
```

如果你本机安装路径不同，再手动覆盖：

```bash
python http_service.py --host 0.0.0.0 --port 8000 --auto-connect --exe-path "D:/broker/xiadan.exe" --tesseract-cmd "D:/Tesseract-OCR/tesseract.exe"
```

可选参数：

- `--host`
- `--port`
- `--debug`
- `--auto-connect`
- `--connect-on-first-use`
- `--exe-path`
- `--tesseract-cmd`
- `--editor-need-type-keys`

### HTTP 路由

- `GET /`
- `GET /health`
- `GET /interfaces`
- `GET|POST /trader/<name>`
- `GET /objects/<handle>`
- `GET|POST /objects/<handle>/<name>`

### HTTP 调用示例

查询余额：

```bash
curl http://127.0.0.1:8000/trader/balance
```

买入股票：

```bash
curl -X POST http://127.0.0.1:8000/trader/buy ^
  -H "Content-Type: application/json" ^
  -d "{\"security\":\"600000\",\"price\":10.5,\"amount\":100}"
```

查询接口列表：

```bash
curl http://127.0.0.1:8000/interfaces
```

`/` 根路由会直接返回当前所有公开接口及示例 payload，适合调试或对接时自描述发现。

## 目录结构

```text
jqktrader/
├── __init__.py
├── api.py
├── clienttrader.py
├── http_service.py
├── grid_strategies.py
├── refresh_strategies.py
├── pop_dialog_handler.py
├── exceptions.py
├── log.py
├── config/
│   └── client.py
└── utils/
    ├── captcha.py
    ├── misc.py
    ├── perf.py
    ├── stock.py
    └── win_gui.py
```

## 常见问题

### 1. 为什么连不上客户端？

优先检查这几项：

- `exe_path` 是否指向真实的客户端进程路径
- 客户端是否已经启动并登录
- 是否以相同权限运行 Python 和交易客户端
- 窗口标题、控件布局是否与当前客户端版本兼容

### 2. 为什么查询数据时失败或卡住？

本项目通过 GUI 自动化和剪贴板读取表格数据，客户端界面变化、弹窗、验证码、最小化窗口都可能影响结果。

### 3. 为什么验证码识别失败？

验证码识别依赖 [utils/captcha.py](/c:/ai/jqktrader/utils/captcha.py:1) 中的逻辑，建议：

- 安装 Tesseract
- 提供正确的 `tesseract_cmd`
- 保持客户端窗口可见
- 必要时手动先完成一次验证码操作

### 4. HTTP 服务为什么不建议直接暴露公网？

因为它本质上是在本机代操桌面交易客户端，没有额外的认证、鉴权、权限隔离和审计设计，更适合作为本地或受控内网服务。

## 风险提示

这是交易自动化工具。请在模拟环境、小资金、非交易高峰时段充分验证后再投入真实场景使用。GUI 自动化天然受客户端版本、窗口焦点、分辨率、弹窗、网络状态等因素影响，不建议在缺乏监控和容错的情况下直接用于高风险实盘。

## 相关文档

- HTTP 专项说明见 [README_HTTP_SERVICE.md](/c:/ai/jqktrader/README_HTTP_SERVICE.md:1)
