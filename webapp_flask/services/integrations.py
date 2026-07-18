# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Integration:
    id: str
    name: str
    kind: str
    url: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


DEFAULT_INTEGRATIONS: tuple[Integration, ...] = (
    Integration(
        id="openwebui",
        name="Open WebUI",
        kind="chat",
        url="",
        description="로컬 Open WebUI 채팅 화면",
    ),
    Integration(
        id="mdlive",
        name="MDlive",
        kind="editor",
        url="https://mdlivepro.vercel.app/",
        description="MDlive 웹 에디터",
    ),
    Integration(
        id="mdpro",
        name="MDpro",
        kind="editor",
        url="https://mdproviewer.vercel.app/",
        description="MDpro 뷰어",
    ),
)
