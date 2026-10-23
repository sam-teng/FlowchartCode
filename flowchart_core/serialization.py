from __future__ import annotations

import json
import os
import pickle

from .models import Project


def save_project(path: str, project: Project) -> None:
    data = project.to_dict()
    if path.endswith(".pickle") or path.endswith(".pkl"):
        with open(path, "wb") as f:
            pickle.dump(data, f)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def load_project(path: str) -> Project:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    if path.endswith(".pickle") or path.endswith(".pkl"):
        with open(path, "rb") as f:
            data = pickle.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("檔案格式錯誤：應為字典結構")
    return Project.from_dict(data)
