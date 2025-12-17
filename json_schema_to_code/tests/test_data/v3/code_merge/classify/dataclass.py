from __future__ import annotations

import re
from dataclasses import dataclass, field

from dataclasses_json import dataclass_json
from explayn_dh_agent.barbara.activities.base.activity_state import ActivityState
from explayn_dh_agent.barbara.db.app_object_definitions.activities.ui_dataclass import (
    UIAction,
)
from explayn_dh_agent.utils import JSONPointer


@dataclass_json
@dataclass(kw_only=True)
class ClassifyInnerObject:
    """
    An object that can be classified into buckets.
    """

    type: str
    uuid: str
    text: str | None = None
    image_url: str | None = None
    hint: str | None = None
    explanation: str | None = None
    mnemonic: str | None = None
    additional_properties: dict = field(default_factory=dict)

    def __post_init__(self):
        """Validate the object after initialization."""
        if not self.type:
            raise ValueError("type field is required")
        if not self.uuid:
            raise ValueError("uuid field is required")
        # Validate UUID format
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        if not re.match(uuid_pattern, self.uuid):
            raise ValueError(f"Invalid UUID format: {self.uuid}")

    def get_property(self, key: str, default=None):
        """Get a property, checking both known fields and additional properties."""
        if hasattr(self, key):
            return getattr(self, key)
        return self.additional_properties.get(key, default)

    def set_property(self, key: str, value):
        """Set a property, using additional_properties for unknown fields."""
        if hasattr(self, key) and key != "additional_properties":
            setattr(self, key, value)
        else:
            self.additional_properties[key] = value


@dataclass_json
@dataclass(kw_only=True)
class ClassifiableObject:
    """
    An object that can be classified with its associated bucket.
    """

    object: ClassifyInnerObject
    bucket: str

    def __post_init__(self):
        """Validate the object after initialization."""
        if not isinstance(self.object, ClassifyInnerObject):
            raise ValueError("object must be a ClassifyInnerObject instance")
        if not self.bucket:
            raise ValueError("bucket field is required")


@dataclass_json
@dataclass(kw_only=True)
class ClassifyUIData:
    """
    Complete UI state for the classify activity view.

    This contains the action template used to send state updates when items
    are moved between buckets.
    """

    buckets: list[ClassifyBucket]
    items: list[ClassifiableObject]
    classified_items: list[ClassifyStateBucket]
    actionTemplate: UIAction


@dataclass_json
@dataclass(kw_only=True)
class ClassifyBucket:
    """
    A bucket/category for classification.
    """

    name: str
    description: str

    def __post_init__(self):
        """Validate the object after initialization."""
        if not self.name:
            raise ValueError("name field is required")
        if not self.description:
            raise ValueError("description field is required")


@dataclass_json
@dataclass(kw_only=True)
class ClassifyStateBucket:
    """
    A bucket in the current state with its items.
    """

    name: str
    items: list[ClassifiableObject] = field(default_factory=list)

    def __post_init__(self):
        """Validate the object after initialization."""
        if not self.name:
            raise ValueError("name field is required")
        if not isinstance(self.items, list):
            raise ValueError("items must be a list")
        for item in self.items:
            if not isinstance(item, ClassifiableObject):
                raise ValueError("All items must be ClassifiableObject instances")


@dataclass_json
@dataclass(kw_only=True)
class ClassifyProblem:
    """
    The classification problem being solved.
    """

    buckets: list[ClassifyBucket]
    items: list[ClassifiableObject]

    def __post_init__(self):
        """Validate the object after initialization."""
        if not isinstance(self.buckets, list):
            raise ValueError("buckets must be a list")
        if len(self.buckets) < 2:
            raise ValueError("Must have at least 2 buckets")
        for bucket in self.buckets:
            if not isinstance(bucket, ClassifyBucket):
                raise ValueError("All bucket items must be ClassifyProblemBuckets instances")

        if not isinstance(self.items, list):
            raise ValueError("items must be a list")
        for item in self.items:
            if not isinstance(item, ClassifiableObject):
                raise ValueError("All items must be ClassifiableObject instances")


@dataclass_json
@dataclass(kw_only=True)
class ClassifyState:
    """
    Current state of the student's classification work.
    """

    buckets: list[ClassifyStateBucket]
    items: list[ClassifiableObject] = field(default_factory=list)

    def __post_init__(self):
        """Validate the object after initialization."""
        if not isinstance(self.buckets, list):
            raise ValueError("buckets must be a list")
        if len(self.buckets) < 2:
            raise ValueError("Must have at least 2 buckets")
        for bucket in self.buckets:
            if not isinstance(bucket, ClassifyStateBucket):
                raise ValueError("All bucket items must be ClassifyStateBuckets instances")

        if not isinstance(self.items, list):
            raise ValueError("items must be a list")
        for item in self.items:
            if not isinstance(item, ClassifiableObject):
                raise ValueError("All items must be ClassifiableObject instances")


@dataclass_json
@dataclass(kw_only=True)
class ClassifyData(ActivityState):
    """
    Complete activity data for classify activity.
    """

    problem: ClassifyProblem = field(default_factory=lambda: ClassifyProblem(buckets=[], items=[]))
    state: ClassifyState = field(default_factory=lambda: ClassifyState(buckets=[], items=[]))
    ui_data: ClassifyUIData | None = None

    @classmethod
    def get_bucket_entry_from_grading_path(cls, path: JSONPointer, state: dict[str, any]) -> any:
        """Get bucket entry from grading path by UUID."""
        uuid = path[0]
        for bucket in state["state"]["buckets"]:
            for item in bucket["items"]:
                if item["object"]["uuid"] == uuid:
                    return item
        return None
