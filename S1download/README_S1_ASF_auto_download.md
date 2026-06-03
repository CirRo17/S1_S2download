# Sentinel-1 本地下载教程

本文档面向第一次使用 `S1_ASF_auto_download.py` 的用户，目标是让你拿到代码后，按步骤就能在自己的电脑上完成 Sentinel-1 原始数据下载和解压。

脚本功能很简单：

1. 按时间范围和 AOI 搜索 Sentinel-1 产品。
2. 下载 ASF 提供的原始 `.zip`。
3. 下载完成后自动解压成 `.SAFE`。
4. 已下载成功的文件会自动跳过，方便反复运行。

---

## 1. 你需要知道的账号体系

Sentinel-1 下载涉及两个网站：

1. Earthdata Login
   - 注册地址：`https://urs.earthdata.nasa.gov/users/new`
   - 这是下载认证的核心账号。

2. ASF
   - 数据搜索和下载入口：`https://search.asf.alaska.edu/`
   - Sentinel-1 相关页面：`https://sentinel1.asf.alaska.edu/`

你必须先有 Earthdata 账号。没有这个账号，脚本无法下载。

建议流程：

1. 先去 `https://urs.earthdata.nasa.gov/users/new` 注册 Earthdata。
2. 注册完成后，用浏览器登录一次。
3. 如果页面要求同意 ASF 应用授权，就先完成授权。

---

## 2. 安装 Python

推荐环境：

1. Windows 10 或 Windows 11
2. Python 3.10 或 Python 3.11

安装时注意：

1. 勾选 `Add Python to PATH`。
2. 安装完成后，在 PowerShell 里运行：

```powershell
python --version
```

如果能看到版本号，说明 Python 已经可用。

---

## 3. 一键安装项目环境

在 `E:\Cursor\Code\Sentinel_AgriVision` 根目录，双击：

```text
一键安装环境.bat
```

或者在 PowerShell 里运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\install_env.ps1
```

这个步骤会做三件事：

1. 创建根目录 `.venv` 虚拟环境
2. 升级 `pip`
3. 安装根目录 `requirements.txt` 里的全部库

安装完成后，你不需要再手动执行 `Activate.ps1`，直接用 `.venv\Scripts\python.exe` 运行脚本即可。

---

## 4. 安装了哪些库

根目录 `requirements.txt` 已统一写好这些库：

- `requests`
- `python-dotenv`
- `rich`
- `tenacity`
- `geopandas`
- `asf_search`
- `tqdm`

含义如下：

1. `requests`
   - 用于网络请求。
2. `python-dotenv`
   - 读取 `.env` 或环境变量。
3. `rich`
   - 提供更清晰的终端输出。
4. `tenacity`
   - 自动重试网络请求。
5. `geopandas`
   - 读取 `.shp` / `.geojson` AOI。
6. `asf_search`
   - ASF 官方推荐的下载会话工具。
7. `tqdm`
   - 下载进度条。

---

## 5. 运行前要改哪些配置

打开文件：

```text
E:\Cursor\Code\Sentinel_AgriVision\S1download\S1_ASF_auto_download.py
```

只改最上面的 `User Config (edit here)` 区域。

常用配置如下：

1. 时间范围

```python
CFG_START_DATE = "2025-05-01"
CFG_END_DATE = "2025-06-01"
```

2. AOI 文件

```python
CFG_AOI_GEOJSON = r"E:\Cursor\Code\Sentinel_AgriVision\S2download\TESTmap.geojson"
```

3. 输出目录

```python
CFG_OUTPUT_DIR = r"E:\Cursor\Code\Sentinel_AgriVision\data\S1\raw_zip"
CFG_EXTRACT_DIR = r"E:\Cursor\Code\Sentinel_AgriVision\data\S1\raw_safe"
```

4. 认证信息

如果你只想用账号密码一键下载，把 token 设空：

```python
CFG_EARTHDATA_USERNAME = "你的Earthdata用户名"
CFG_EARTHDATA_PASSWORD = "你的Earthdata密码"
CFG_EARTHDATA_TOKEN = ""
```

这是推荐方案。token 会过期，账号密码更适合长期使用。

---

## 6. 如何启动

进入 `S1download` 目录：

```powershell
cd /d E:\Cursor\Code\Sentinel_AgriVision\S1download
```

先只搜索，不下载：

```powershell
..\.\.venv\Scripts\python.exe -u .\S1_ASF_auto_download.py --search-only --max-results 5
```

正式下载：

```powershell
..\.\.venv\Scripts\python.exe -u .\S1_ASF_auto_download.py
```

如果你不想进目录，也可以直接运行完整路径：

```powershell
E:\Cursor\Code\Sentinel_AgriVision\.venv\Scripts\python.exe -u E:\Cursor\Code\Sentinel_AgriVision\S1download\S1_ASF_auto_download.py
```

---

## 7. 脚本会自动做什么

运行后，脚本会按这个流程执行：

1. 检查账号密码或 token。
2. 按时间范围和 AOI 搜索 Sentinel-1 产品。
3. 输出搜索结果前几条，方便你确认。
4. 下载每个产品的原始 zip。
5. 显示下载进度条。
6. 下载成功后自动解压到 `.SAFE`。
7. 如果文件已经存在，会直接跳过。

---

## 8. 只搜索不下载

第一次建议先搜一下，确认产品列表没问题：

```powershell
E:\Cursor\Code\Sentinel_AgriVision\.venv\Scripts\python.exe -u E:\Cursor\Code\Sentinel_AgriVision\S1download\S1_ASF_auto_download.py --search-only --max-results 10
```

如果你想临时改时间范围，也可以直接传参数：

```powershell
E:\Cursor\Code\Sentinel_AgriVision\.venv\Scripts\python.exe -u E:\Cursor\Code\Sentinel_AgriVision\S1download\S1_ASF_auto_download.py --search-only --start-date 2025-05-11 --end-date 2025-05-11
```

---

## 9. AOI 支持什么格式

脚本当前支持：

1. `.geojson`
2. `.json`
3. `.shp`

推荐使用：

1. 小范围测试先用 `.geojson`
2. 大范围和已有矢量数据可以用 `.shp`

注意：

1. 坐标系最好是 WGS84 / EPSG:4326
2. 坐标顺序必须是 `[lon, lat]`
3. SHP 需要装 `geopandas`

---

## 10. 下载目录怎么放

建议按这个结构存：

```text
E:\Cursor\Code\Sentinel_AgriVision\data\S1\
  raw_zip\
    *.zip
  raw_safe\
    *.SAFE\
```

这样后续如果要做预处理、配准、特征计算，会很清晰。

---

## 11. 失败后怎么重跑

这个脚本适合反复运行，不需要你手工记住哪些下载过。

它会：

1. 跳过已经存在的完整 zip
2. 跳过已经存在的 `.SAFE`
3. 失败的文件下次继续重试

所以你只要重新执行同一条命令即可。

---

## 12. 常见问题

1. 不要直接运行 `Activate.ps1`
   - PowerShell 容易被执行策略拦住。
   - 直接用 `.venv\Scripts\python.exe` 就行。

2. 浏览器显示已登录，不代表脚本就能下载
   - 浏览器 cookie 和 Python 会话不是一回事。

3. token 会过期
   - 如果你使用 token，需要定期更新。
   - 只用账号密码时，通常更省事。

4. 看到 401
   - 检查账号密码
   - 确认是否完成 Earthdata / ASF 授权
   - 重新运行脚本即可

---

## 13. 最推荐的首次使用流程

1. 注册 Earthdata 账号。
2. 安装 Python 3.10 或 3.11。
3. 双击 `一键安装环境.bat`。
4. 在 `S1_ASF_auto_download.py` 顶部写好账号密码，`CFG_EARTHDATA_TOKEN = ""`。
5. 先运行 `--search-only` 检查产品。
6. 再正式运行下载。

