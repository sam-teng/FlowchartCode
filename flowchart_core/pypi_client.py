from __future__ import annotations

import html
import json
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

from .module_inspector import list_installed_distributions

USER_AGENT = "FlowChartCode/1.0 (+local tool)"
DEFAULT_TIMEOUT = 8


@dataclass
class PackageInfo:
    name: str
    version: str = ""
    summary: str = ""
    description: str = ""
    author: str = ""
    home_page: str = ""
    requires_python: str = ""
    requires_dist: list = field(default_factory=list)


@dataclass
class SearchResult:
    name: str
    version: str = ""
    summary: str = ""


class PyPIClientError(Exception):
    pass


def _fetch(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def get_package_info(name: str, timeout: int = DEFAULT_TIMEOUT) -> Optional[PackageInfo]:
    name = (name or "").strip()
    if not name:
        return None
    url = f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json"
    try:
        raw = _fetch(url, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    info = data.get("info") or {}
    return PackageInfo(
        name=info.get("name") or name,
        version=info.get("version") or "",
        summary=(info.get("summary") or "").strip(),
        description=(info.get("description") or "")[:2000],
        author=info.get("author") or info.get("author_email") or "",
        home_page=info.get("home_page") or info.get("project_url") or f"https://pypi.org/project/{name}/",
        requires_python=info.get("requires_python") or "",
        requires_dist=list(info.get("requires_dist") or [])[:30],
    )


_NAME_SNIPPET = re.compile(
    r'package-snippet__name[^>]*>([^<]+)<.*?'
    r'package-snippet__version[^>]*>([^<]+)<.*?'
    r'package-snippet__description[^>]*>([^<]+)<',
    re.S,
)


def search_packages(query: str, timeout: int = DEFAULT_TIMEOUT) -> list[SearchResult]:
    query = (query or "").strip()
    if not query:
        return []
    results: list[SearchResult] = []
    exact = get_package_info(query, timeout=timeout)
    if exact is not None:
        results.append(SearchResult(exact.name, exact.version, exact.summary))
    url = f"https://pypi.org/search/?q={urllib.parse.quote(query)}&page=1"
    try:
        raw = _fetch(url, timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return results
    seen = {r.name.lower() for r in results}
    for match in _NAME_SNIPPET.finditer(raw):
        name = html.unescape(match.group(1)).strip()
        version = html.unescape(match.group(2)).strip()
        summary = html.unescape(match.group(3)).strip()
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        results.append(SearchResult(name, version, summary))
        if len(results) >= 30:
            break
    if not results:
        for match in re.finditer(
                r'href="/project/([^"/]+)/"[^>]*>\s*([^<]+?)\s*</a>', raw):
            name = html.unescape(match.group(1)).strip()
            if name.lower() not in seen:
                seen.add(name.lower())
                results.append(SearchResult(name))
                if len(results) >= 30:
                    break
    return results


def list_installed() -> list[SearchResult]:
    return [
        SearchResult(name=name, version=version)
        for name, version in list_installed_distributions()
    ]


def install_package(name: str,
                    on_output: Optional[Callable[[str], None]] = None,
                    timeout: int = 600) -> tuple[bool, str]:
    name = (name or "").strip()
    if not name or not re.match(r"^[\w\.\-_]+$", name):
        return False, "套件名稱無效"
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", name]
    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        return False, f"無法啟動 pip：{exc}"
    collected: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            collected.append(line)
            if on_output:
                on_output(line.rstrip())
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        return False, "安裝逾時"
    output = "".join(collected)
    if process.returncode == 0:
        return True, output[-2000:]
    return False, output[-2000:] or f"pip 退出碼 {process.returncode}"
