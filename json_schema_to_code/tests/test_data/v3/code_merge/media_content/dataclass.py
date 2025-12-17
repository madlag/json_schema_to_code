"""Shared media content types for activities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass(kw_only=True)
class MediaContentText:
    """Text-only content."""

    text: str
    type: Literal["text"] = "text"


@dataclass_json
@dataclass(kw_only=True)
class MediaContentImage:
    """Image-only content."""

    image_url: str
    type: Literal["image"] = "image"


@dataclass_json
@dataclass(kw_only=True)
class MediaContentTextAndImage:
    """Text and image content."""

    text: str
    image_url: str
    type: Literal["text_and_image"] = "text_and_image"


# Union type for media content
MediaContentType = MediaContentImage | MediaContentText | MediaContentTextAndImage
