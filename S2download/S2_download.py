"""
Sentinel-2 数据自动下载脚本，数据源为 Copernicus Data Space
时间：2026/05/21
版本：V1

"""

import json
import logging
import netrc
import os
import re
import sys
import threading
import argparse
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    import geopandas as gpd
except ImportError:
    gpd = None


SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(SCRIPT_DIR / "download.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
console = Console()

# =========================
# 用户参数：通常只需要改这一段
# =========================
startDate = "2025-05-15"
endDate = "2025-12-30"
satellite = "SENTINEL-2"
# satellite = "SENTINEL-1"

# 产品名称过滤。
contains_str = ""
# contains_str = "REQ"

roi_geojson = "CBHmap.geojson"
# roi_geojson = "JZ_qy.shp"

output_dir = "E:/Cursor/Code/Sentinel_AgriVision/data/S2/DANGYANG/raw_zip"
extract_dir = "E:/Cursor/Code/Sentinel_AgriVision/data/S2/DANGYANG/raw_safe"

email = ""
password = ""

limit = 50
max_workers = 2


def parse_args():
    parser = argparse.ArgumentParser(description="Search and download Sentinel products from CDSE.")
    parser.add_argument("--start-date", default=os.getenv("CDSE_START_DATE", startDate), help="Start date, for example 2025-01-01.")
    parser.add_argument("--end-date", default=os.getenv("CDSE_END_DATE", endDate), help="End date, for example 2025-04-01.")
    parser.add_argument("--satellite", default=os.getenv("CDSE_SATELLITE", satellite), help="SENTINEL-1 or SENTINEL-2.")
    parser.add_argument("--contains", default=os.getenv("CDSE_CONTAINS", contains_str), help="Optional product name filter, for example L2A or T49RGQ.")
    parser.add_argument("--s1-mode", default=os.getenv("CDSE_S1_MODE", "IW"), help="Sentinel-1 instrument mode, for example IW.")
    parser.add_argument("--s1-pol", default=os.getenv("CDSE_S1_POL", "VH"), help="Sentinel-1 polarization to require, for example VH or VV.")
    parser.add_argument("--s1-product", default=os.getenv("CDSE_S1_PRODUCT", "GRD"), help="Sentinel-1 product type to require, for example GRD.")
    parser.add_argument("--aoi", default=os.getenv("CDSE_AOI", os.getenv("CDSE_AOI_GEOJSON", roi_geojson)), help="AOI file for area search: .geojson, .json, or .shp.")
    parser.add_argument("--aoi-geojson", dest="aoi", help="Deprecated alias of --aoi.")
    parser.add_argument("--aoi-simplify", type=float, default=float(os.getenv("CDSE_AOI_SIMPLIFY", "0.0001")), help="Simplify AOI geometry tolerance in degrees. Use 0 to disable.")
    parser.add_argument("--limit", type=int, default=int(os.getenv("CDSE_LIMIT", str(limit))), help="Maximum products to search.")
    parser.add_argument("--output-dir", default=os.getenv("CDSE_OUTPUT_DIR", output_dir), help="Directory for downloaded zip files.")
    parser.add_argument("--extract-dir", default=os.getenv("CDSE_EXTRACT_DIR", extract_dir), help="Directory for extracted SAFE folders.")
    parser.add_argument("--no-extract", action="store_true", help="Download zip files without extracting them.")
    parser.add_argument("--max-workers", type=int, default=int(os.getenv("CDSE_MAX_WORKERS", str(max_workers))), help="Download workers, capped at 2.")
    parser.add_argument("--search-only", action="store_true", help="Only search and list products; do not download.")
    return parser.parse_args()


def collection_from_satellite(name, product_level):
    """把简写卫星参数映射为 Copernicus STAC 集合名。"""
    name = (name or "").upper()
    product_level = (product_level or "").upper()

    if name == "SENTINEL-2":
        return "sentinel-2-l1c" if "L1C" in product_level else "sentinel-2-l2a"
    if name == "SENTINEL-1":
        return "sentinel-1"

    raise ValueError(f"不支持的卫星类型：{name}")


def _parse_contains_keywords(contains_value: str):
    """
    Parse --contains value. Supports:
    - Single keyword: "REQ"
    - Comma-separated: "REQ,REP"
    - Whitespace-separated: "REQ REP"
    Matching is case-insensitive and uses substring containment against product id.
    """
    if not contains_value:
        return []
    raw = str(contains_value).strip()
    if not raw:
        return []
    # Split by comma and/or whitespace.
    parts = []
    for token in raw.replace(",", " ").split():
        t = token.strip()
        if t:
            parts.append(t)
    return parts


class CDSEClient:
    """Copernicus Data Space 客户端。"""

    IDENTITY_HOST = "identity.dataspace.copernicus.eu"

    def __init__(self, username=None, password=None):
        netrc_username, netrc_password = self._read_netrc_credentials()
        self.username = username or os.getenv("CDSE_USERNAME") or netrc_username
        self.password = password or os.getenv("CDSE_PASSWORD") or netrc_password
        self.token = None
        self.base_url = f"https://{self.IDENTITY_HOST}/auth/realms/CDSE"
        self._token_lock = threading.Lock()

        if not self.username or not self.password:
            raise RuntimeError("缺少 Copernicus 账号密码。请在脚本顶部填写 email/password，或配置 .env/_netrc。")

    @classmethod
    def _read_netrc_credentials(cls):
        """从 Windows _netrc 或 Linux/macOS .netrc 读取账号密码。"""
        candidate_paths = [
            Path.home() / "_netrc",
            Path.home() / ".netrc",
        ]

        for path in candidate_paths:
            if not path.exists():
                continue

            try:
                auth = netrc.netrc(str(path)).authenticators(cls.IDENTITY_HOST)
            except (netrc.NetrcParseError, OSError) as exc:
                logger.warning("读取 netrc 文件失败 %s: %s", path, exc)
                continue

            if auth:
                login, _, password = auth
                return login, password

        return None, None

    def login(self):
        """登录并刷新 Token。多线程下载时同一时间只允许一个线程刷新。"""
        with self._token_lock:
            console.print("[bold green]正在登录 Copernicus Data Space...[/bold green]")
            token_url = f"{self.base_url}/protocol/openid-connect/token"
            response = requests.post(
                token_url,
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                    "client_id": "cdse-public",
                },
                timeout=30,
            )

            if response.status_code == 200:
                self.token = response.json()["access_token"]
                console.print(f"[bold green]登录成功，Token 长度：{len(self.token)}[/bold green]")
                return True

            console.print(f"[bold red]登录失败：{response.status_code} {response.text}[/bold red]")
            return False

    def _auth_headers(self, extra_headers=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _request_with_token_refresh(self, method, url, **kwargs):
        """发送请求；遇到 401 时自动刷新 Token 并重试一次。"""
        headers = kwargs.pop("headers", None)
        response = requests.request(method, url, headers=self._auth_headers(headers), **kwargs)

        if response.status_code == 401:
            console.print("[yellow]Token 已过期，正在重新登录后重试...[/yellow]")
            if not self.login():
                return response
            response = requests.request(method, url, headers=self._auth_headers(headers), **kwargs)

        return response

    @staticmethod
    def _load_intersects(aoi_path, simplify_tolerance=0.0001):
        """读取 GeoJSON 区域，用于 STAC intersects 空间过滤。"""
        if not aoi_path:
            return None

        path = Path(aoi_path)
        if not path.is_absolute():
            path = SCRIPT_DIR / path

        suffix = path.suffix.lower()
        if suffix == ".shp":
            if gpd is None:
                raise RuntimeError("读取 SHP 需要安装 geopandas：pip install geopandas")
            gdf = gpd.read_file(path)
            if gdf.empty:
                raise ValueError(f"AOI 文件没有要素：{path}")
            if gdf.crs is None:
                raise ValueError(f"SHP 缺少坐标系信息，请先定义坐标系：{path}")
            gdf = gdf.to_crs("EPSG:4326")
            gdf["geometry"] = gdf.geometry.buffer(0)
            geometry = gdf.geometry.union_all()
            if simplify_tolerance and simplify_tolerance > 0:
                geometry = geometry.simplify(simplify_tolerance, preserve_topology=True)
            return geometry.__geo_interface__

        if suffix not in (".geojson", ".json"):
            raise ValueError(f"不支持的 AOI 文件格式：{path.suffix}。请使用 .geojson、.json 或 .shp")

        with path.open("r", encoding="utf-8") as file_obj:
            geojson = json.load(file_obj)

        if geojson.get("type") == "FeatureCollection":
            features = geojson.get("features", [])
            if not features:
                raise ValueError(f"AOI 文件中没有 Feature：{path}")
            return features[0]["geometry"]

        if geojson.get("type") == "Feature":
            return geojson["geometry"]

        return geojson

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.RequestException,
        )),
        reraise=True,
    )
    def search_products(
        self,
        collection="sentinel-2-l2a",
        start_date=None,
        end_date=None,
        limit=10,
        aoi_path=None,
        aoi_simplify=0.0001,
        s1_mode="IW",
        s1_pol="VH",
        s1_product="GRD",
    ):
        """搜索产品。没有指定日期时默认搜索最近 1 天。"""
        if end_date is None:
            end_date = datetime.now(timezone.utc).date().isoformat()
        if start_date is None:
            start_date = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        console.print(f"[bold blue]正在搜索 {collection}：{start_date} 至 {end_date}[/bold blue]")

        payload = {
            "collections": [collection],
            "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
            "limit": limit,
            "sortby": [{"field": "properties.datetime", "direction": "desc"}],
        }
        if collection == "sentinel-1":
            payload["query"] = {
                "sar:instrument_mode": {"eq": s1_mode},
                "s1:product_type": {"eq": s1_product},
            }

        intersects = self._load_intersects(aoi_path, aoi_simplify)
        if intersects:
            payload["intersects"] = intersects
            console.print(f"[bold blue]已启用区域过滤：{aoi_path}[/bold blue]")

        response = self._request_with_token_refresh(
            "POST",
            "https://stac.dataspace.copernicus.eu/v1/search",
            json=payload,
            timeout=180,
        )

        if response.status_code != 200:
            console.print(f"[bold red]搜索失败：{response.status_code} {response.text}[/bold red]")
            return []

        try:
            features = response.json().get("features", [])
        except ValueError:
            content_type = response.headers.get("Content-Type", "unknown")
            console.print(f"[bold red]解析搜索结果失败，接口返回的不是 JSON：{content_type}[/bold red]")
            return []

        console.print(f"[bold green]找到 {len(features)} 个产品[/bold green]")
        for index, item in enumerate(features[:5], 1):
            props = item.get("properties", {})
            console.print(f"  {index}. {item.get('id', 'N/A')}")
            console.print(f"     日期：{props.get('datetime', 'N/A')}")
        return features

    def _remote_size(self, download_url):
        """读取远端文件大小；服务器不返回时返回 None。"""
        try:
            response = self._request_with_token_refresh("HEAD", download_url, allow_redirects=True, timeout=60)
            if response.status_code in (200, 206):
                length = response.headers.get("Content-Length")
                return int(length) if length else None
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout, ValueError) as exc:
            logger.warning("读取远端文件大小失败：%s", exc)
        return None

    @staticmethod
    def _zip_download_url(item):
        """从 STAC item 的资产链接中提取整包 SAFE zip 下载地址。"""
        product_id = item.get("id")
        if not product_id:
            return None

        for asset in item.get("assets", {}).values():
            href = asset.get("alternate", {}).get("https", {}).get("href", "")
            match = re.search(r"Products\(([^)]+)\)", href)
            if match:
                uuid = match.group(1)
                return f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({uuid})/$value"

        return None

    @staticmethod
    def extract_safe_zip(zip_path, extract_dir):
        zip_path = Path(zip_path)
        extract_dir = Path(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        expected_safe_dir = extract_dir / f"{zip_path.stem}.SAFE"
        if expected_safe_dir.exists():
            console.print(f"  [green]已存在解压目录，跳过：{expected_safe_dir}[/green]")
            return True

        console.print(f"  正在解压：{zip_path.name} -> {extract_dir}")
        try:
            with zipfile.ZipFile(zip_path) as zip_obj:
                zip_obj.extractall(extract_dir)
        except zipfile.BadZipFile:
            console.print(f"  [red]zip 文件损坏，无法解压：{zip_path}[/red]")
            logger.exception("zip 文件损坏，无法解压：%s", zip_path)
            return False
        except OSError:
            console.print(f"  [red]解压失败：{zip_path}[/red]")
            logger.exception("解压失败：%s", zip_path)
            return False

        if expected_safe_dir.exists():
            console.print(f"  [green]解压完成：{expected_safe_dir}[/green]")
            return True

        console.print(f"  [yellow]解压完成，但未找到预期目录：{expected_safe_dir}[/yellow]")
        return True

    @staticmethod
    def is_valid_zip(zip_path):
        try:
            with zipfile.ZipFile(zip_path) as zip_obj:
                return zip_obj.testzip() is None
        except (zipfile.BadZipFile, OSError):
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.RequestException,
        )),
        reraise=True,
    )
    def download_product(self, product_id, download_url, output_dir="./data", extract_dir=None):
        """下载单个产品，处理 Token 刷新、网络重试和不完整文件。"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{product_id}.zip"
        part_path = output_dir / f"{product_id}.zip.part"
        expected_size = self._remote_size(download_url)

        if output_path.exists():
            local_size = output_path.stat().st_size
            size_ok = expected_size is None or local_size == expected_size
            zip_ok = self.is_valid_zip(output_path)
            if size_ok and zip_ok:
                console.print(f"  [green]已存在完整文件，跳过：{output_path}[/green]")
                if extract_dir:
                    return self.extract_safe_zip(output_path, extract_dir)
                return True
            console.print(f"  [yellow]已有 zip 大小不一致，删除后重新下载：{output_path}[/yellow]")
            output_path.unlink()

        if part_path.exists():
            console.print(f"  [yellow]删除未完成文件：{part_path}[/yellow]")
            part_path.unlink()

        console.print(f"  正在下载：{product_id}")
        response = self._request_with_token_refresh(
            "GET",
            download_url,
            stream=True,
            timeout=300,
        )

        if response.status_code not in (200, 206):
            console.print(f"  [red]下载失败：{product_id}，HTTP {response.status_code}[/red]")
            logger.error("下载失败：%s，HTTP %s，%s", product_id, response.status_code, response.text[:500])
            return False

        total_size = expected_size or int(response.headers.get("Content-Length", 0) or 0)
        downloaded = 0

        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task(f"下载 {product_id}", total=total_size or None)
            with part_path.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, completed=downloaded)

        final_size = part_path.stat().st_size
        if expected_size is not None and final_size != expected_size:
            console.print(
                f"  [red]文件大小不一致，删除临时文件：本地 {final_size}，远端 {expected_size}[/red]"
            )
            part_path.unlink(missing_ok=True)
            return False

        part_path.replace(output_path)
        console.print(f"  [green]下载完成：{output_path}[/green]")
        logger.info("下载完成：%s -> %s", product_id, output_path)
        if extract_dir:
            return self.extract_safe_zip(output_path, extract_dir)
        return True

    def batch_download(self, product_items, output_dir="./data", extract_dir=None, max_workers=3):
        """批量下载产品。并发数最高限制为 2，避免被服务器限流。"""
        max_workers = max(1, min(int(max_workers), 2))
        console.print(f"[bold green]开始批量下载：{len(product_items)} 个产品[/bold green]")
        console.print(f"[bold blue]输出目录：{output_dir}[/bold blue]")
        console.print(f"[bold blue]并发线程：{max_workers}[/bold blue]")
        console.print()

        success_count = 0
        fail_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.download_product, item["id"], item["download_url"], output_dir, extract_dir): item["id"]
                for item in product_items
            }

            for future in as_completed(futures):
                product_id = futures[future]
                try:
                    if future.result():
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as exc:
                    console.print(f"[bold red]下载异常：{product_id} - {exc}[/bold red]")
                    logger.exception("下载异常：%s", product_id)
                    fail_count += 1

        console.print()
        console.print("=" * 60)
        console.print("[bold]下载统计：[/bold]")
        console.print(f"  成功：{success_count}")
        console.print(f"  失败：{fail_count}")
        console.print(f"  总计：{len(product_items)}")
        console.print("=" * 60)
        logger.info("下载统计：成功=%s 失败=%s 总计=%s", success_count, fail_count, len(product_items))


def main():
    args = parse_args()
    console.print("[bold cyan]Sentinel-2 数据自动下载工具[/bold cyan]")
    console.print()

    try:
        client = CDSEClient(
            username=email or None,
            password=password or None,
        )
    except RuntimeError as exc:
        console.print(f"[bold red]{exc}[/bold red]")
        sys.exit(1)

    if not client.login():
        sys.exit(1)

    # collection only depends on satellite + product level, not name filter
    collection = collection_from_satellite(args.satellite, "")
    products = client.search_products(
        collection=os.getenv("CDSE_COLLECTION", collection),
        start_date=args.start_date,
        end_date=args.end_date,
        limit=args.limit,
        aoi_path=args.aoi,
        aoi_simplify=args.aoi_simplify,
        s1_mode=args.s1_mode,
        s1_pol=args.s1_pol,
        s1_product=args.s1_product,
    )

    if not products:
        console.print("[bold red]没有搜索到产品。[/bold red]")
        sys.exit(1)

    product_items = [
        {"id": item.get("id"), "download_url": client._zip_download_url(item)}
        for item in products
        if item.get("id")
    ]
    if args.contains:
        keywords = _parse_contains_keywords(args.contains)
        if keywords:
            product_items = [
                item
                for item in product_items
                if any(k.lower() in item.get("id", "").lower() for k in keywords)
            ]
        console.print(f"[bold blue]产品名过滤：{args.contains}，匹配 {len(product_items)} 个产品[/bold blue]")

    product_items = [item for item in product_items if item["download_url"]]
    console.print(f"[bold blue]可下载产品：{len(product_items)} 个[/bold blue]")

    if args.search_only:
        console.print("[bold yellow]仅搜索模式：不会下载产品。[/bold yellow]")
        for index, item in enumerate(product_items, 1):
            console.print(f"  {index}. {item['id']}")
        return

    if not product_items:
        console.print("[bold red]没有产品匹配过滤条件，或没有找到可用下载链接。[/bold red]")
        sys.exit(1)

    client.batch_download(
        product_items,
        output_dir=args.output_dir,
        extract_dir=None if args.no_extract else args.extract_dir,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
