# Sentinel-1 / Sentinel-2 Downloader

本项目包含两个独立下载脚本：

- `S1download/S1_ASF_auto_download.py`：从 Alaska Satellite Facility 下载 Sentinel-1 数据。
- `S2download/S2_download.py`：从 Copernicus Data Space 下载 Sentinel-2 数据。

所有 Python 依赖统一放在根目录 `requirements.txt`。

## 目录结构

```text
S1_S2download/
├─ S1download/
│  ├─ S1_ASF_auto_download.py
│  └─ README_S1_ASF_auto_download.md
├─ S2download/
│  ├─ S2_download.py
│  └─ README_S2_download.md
├─ requirements.txt
├─ install_env.ps1
├─ 一键安装环境.bat
└─ README.md
```

## 环境安装

先安装 Python 3.10 或更高版本，并勾选 `Add Python to PATH`。

在项目根目录双击：

```bat
一键安装环境.bat
```

或者在 PowerShell 里运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_env.ps1
```

脚本会自动创建根目录 `.venv`，并安装 `requirements.txt` 中的全部依赖。

## 账号配置

不要把账号密码写进 GitHub 仓库。推荐使用环境变量或 `_netrc`。

Sentinel-2 / Copernicus Data Space：

先在 Copernicus Data Space 注册账号：

```text
https://dataspace.copernicus.eu/
```

注册并登录后，使用该网站的账号和密码配置环境变量：

```powershell
setx CDSE_USERNAME "你的Copernicus账号"
setx CDSE_PASSWORD "你的Copernicus密码"
```

Sentinel-1 / Earthdata：

```powershell
setx EARTHDATA_USERNAME "你的Earthdata账号"
setx EARTHDATA_PASSWORD "你的Earthdata密码"
```

也可以在运行 Sentinel-1 脚本时传入 `--token`、`--username`、`--password`。

## 运行 Sentinel-2

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py
```

常用参数示例：

```powershell
.\.venv\Scripts\python.exe -u .\S2download\S2_download.py --start-date 2025-05-15 --end-date 2025-12-30 --aoi .\S2download\CBHmap.geojson --output-dir D:\S2\raw_zip --extract-dir D:\S2\raw_safe
```

## 运行 Sentinel-1

```powershell
.\.venv\Scripts\python.exe -u .\S1download\S1_ASF_auto_download.py
```

常用参数示例：

```powershell
.\.venv\Scripts\python.exe -u .\S1download\S1_ASF_auto_download.py --start-date 2025-01-01 --end-date 2025-12-30 --aoi-geojson D:\ROI\area.geojson --output-dir D:\S1\raw_zip --extract-dir D:\S1\raw_safe
```

## 上传 GitHub 前确认

仓库中应保留源码、README、安装脚本和根目录 `requirements.txt`。

不要上传这些本机生成文件：

- `.venv/`
- `.vscode/`
- `__pycache__/`
- `download.log`
- `.env`
- 已下载的 `.zip`、`.SAFE` 数据目录

## 详细说明

- Sentinel-1 详细文档：`S1download/README_S1_ASF_auto_download.md`
- Sentinel-2 详细文档：`S2download/README_S2_download.md`
