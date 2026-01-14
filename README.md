# live-spider

用于下载 B 站直播流的简易脚本，支持按分片实时拼接输出文件。

## 运行环境

- Python 3.10+（以 `pyproject.toml` 为准）
- Windows（当前脚本与路径默认偏向 Windows）

## 安装依赖

使用 uv（推荐）：

```bash
uv sync
```

不使用 uv：

```bash
python -m pip install -e .
```

## 使用方式

1) 扫码登录并保存 cookies：

```bash
uv run python spider/get_cookie.py
```

或（不使用 uv）：

```bash
python spider/get_cookie.py
```

成功后会生成 `cookie/bilibili.cookies`。

2) 运行下载脚本：

```bash
uv run python spider/spider.py
```

或（不使用 uv）：

```bash
python spider/spider.py
```

## 配置与说明

- 直播间 UID：默认在 `spider/spider.py` 中 `get_uid_live_id("474595627")`，需要下载其它主播请替换为目标 UID。
- 画质：脚本会自动选择最高可用画质。
- 分片大小：`download_live` 的 `size_MB` 默认 20MB，可在 `spider/spider.py` 中调整。

## 输出目录

- 临时分片：`temp/<room_id>/`
- 最终文件：`downloads/<uname>/`（按主播昵称归档）

## 注意事项

- 请勿提交真实 cookies / `SESSDATA` 到仓库。
- 直播未开播会直接退出；接口返回异常会有日志提示。

## 免责声明

本项目仅用于学习与研究，请遵守相关平台协议与法律法规。
