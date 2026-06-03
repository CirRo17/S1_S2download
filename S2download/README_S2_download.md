# Sentinel-2 自动下载说明

本文档说明如何使用 `S2_download.py` 从 Copernicus Data Space 下载 Sentinel-2 数据，并自动解压为 `.SAFE` 文件夹。

## 1. 环境安装

在项目根目录运行：

```powershell
.\一键安装环境.bat
```

或者：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_env.ps1
```

安装脚本会在项目根目录创建 `.venv`，并安装根目录 `requirements.txt` 中的全部依赖。

## 2. 账号配置

Sentinel-2 数据来自 Copernicus Data Space。先在下面的网站注册账号：

```text
https://dataspace.copernicus.eu/
```

注册并登录成功后，使用该网站的账号和密码运行脚本。

请不要把账号密码写进脚本后上传 GitHub。推荐使用环境变量：

```powershell
setx CDSE_USERNAME "你的Copernicus账号"
setx CDSE_PASSWORD "你的Copernicus密码"
```

重新打开一个 PowerShell 窗口后再运行脚本。

也可以使用 Windows `_netrc` 文件，路径通常是：

```text
C:\Users\你的用户名\_netrc
```

内容示例：

```text
machine identity.dataspace.copernicus.eu login 你的Copernicus账号 password 你的Copernicus密码
```

## 3. 准备 AOI 文件

脚本支持以下 AOI 格式：

- `.geojson`
- `.json`
- `.shp`

如果使用相对路径，脚本会从 `S2download` 目录下查找 AOI 文件。

## 4. 查看帮助

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --help
```

## 5. 先搜索不下载

第一次使用建议先运行 `--search-only`，确认时间范围、AOI 和产品数量是否正确：

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --search-only --aoi .\S2download\TESTmap.geojson --start-date 2025-05-01 --end-date 2025-06-01 --limit 10
```

## 6. 正式下载

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --aoi .\S2download\TESTmap.geojson --start-date 2025-05-01 --end-date 2025-06-01 --limit 10
```

指定输出目录：

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --aoi .\S2download\TESTmap.geojson --output-dir D:\S2\raw_zip --extract-dir D:\S2\raw_safe
```

只下载 zip，不自动解压：

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --no-extract
```

## 7. 常用参数

- `--start-date`：开始日期，例如 `2025-05-01`。
- `--end-date`：结束日期，例如 `2025-06-01`。
- `--aoi`：AOI 文件路径。
- `--contains`：产品名称过滤关键字，例如轨道号、瓦片号或 `L2A`。
- `--limit`：最大搜索数量。
- `--output-dir`：zip 下载目录。
- `--extract-dir`：`.SAFE` 解压目录。
- `--max-workers`：下载线程数，脚本会限制并发，避免请求过多。
- `--search-only`：只搜索并列出产品，不下载。
- `--no-extract`：只下载 zip，不解压。

## 8. 运行流程

脚本会依次执行：

1. 读取 Copernicus Data Space 账号。
2. 登录并获取 Token。
3. 根据日期、AOI、产品类型搜索 Sentinel-2 产品。
4. 按产品 ID 过滤可下载产品。
5. 下载 zip 文件到 `output_dir`。
6. 下载完成后自动解压到 `extract_dir`。
7. 已存在的 zip 或 `.SAFE` 会自动跳过。

## 9. 常见问题

如果提示缺少账号密码，检查是否已经设置：

```powershell
echo $env:CDSE_USERNAME
echo $env:CDSE_PASSWORD
```

如果刚刚执行过 `setx`，需要重新打开 PowerShell 窗口。

如果 AOI 文件找不到，请使用绝对路径，或把 AOI 文件放到 `S2download` 目录下。

如果读取 `.shp` 失败，请确认 `geopandas` 已经安装，并且 `.shp/.shx/.dbf/.prj` 等配套文件齐全。

## 10. 上传 GitHub 前检查

不要上传：

- `.venv/`
- `.vscode/`
- `__pycache__/`
- `.env`
- `download.log`
- 下载得到的 `.zip`
- 解压得到的 `.SAFE`

根目录 `.gitignore` 已经包含这些规则。

学习记录：尝试修改代码并推送到github