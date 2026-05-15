from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TrClass(str, Enum):
    REALTIME = "realtime"
    QUERY = "query"
    CONTINUOUS = "continuous"


class Market(str, Enum):
    STOCK = "stock"
    FUTURES_OPTIONS = "futures_options"
    OVERSEAS_FUTURES = "overseas_futures"
    OVERSEAS_STOCK = "overseas_stock"
    SECTOR = "sector"
    ETC = "etc"
    AUTH = "auth"


class StopCondition(str, Enum):
    EMPTY_VALUE = "empty_value"
    ZERO_IDX = "zero_idx"
    HEADER_FLAG = "header_flag"


class FieldSpec(BaseModel):
    name: str = Field(..., alias="n")
    korean_name: str = Field(default="", alias="k")
    type_code: str = Field(default="A0001", alias="t")
    length: str = Field(default="", alias="l")
    is_required: bool = Field(default=False, alias="r")

    model_config = {"populate_by_name": True}

    @property
    def python_type(self) -> type:
        if "." in self.length:
            return float
        tc = self.type_code
        if tc in ("A0003", "A0004", "int"):
            return int
        if tc in ("A0005", "A0006", "float"):
            return float
        return str

    @property
    def max_length(self) -> int | None:
        if not self.length:
            return None
        return int(self.length.split(".")[0])


class BlockSpec(BaseModel):
    name: str = Field(..., alias="n")
    fields: list[FieldSpec] = Field(default_factory=list, alias="f")
    is_repeating: bool = Field(default=False, alias="r")

    model_config = {"populate_by_name": True}

    def field_names(self) -> set[str]:
        return {f.name for f in self.fields}

    def required_fields(self) -> list[FieldSpec]:
        return [f for f in self.fields if f.is_required]

    def get_field(self, name: str) -> FieldSpec | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None


class ContinuationSpec(BaseModel):
    data_block: str = Field(..., alias="db")
    continuation_block: str = Field(..., alias="cb")
    key_fields: list[str] = Field(default_factory=list, alias="kf")
    stop_condition: StopCondition = Field(default=StopCondition.EMPTY_VALUE, alias="stop")

    model_config = {"populate_by_name": True}

    def extract_next_params(
        self,
        response_body: dict[str, Any],
        current_params: dict[str, Any],
        in_block_key: str,
    ) -> tuple[dict[str, Any], bool]:
        cont_data = response_body.get(self.continuation_block)
        if not isinstance(cont_data, dict):
            return current_params, False

        updated = dict(current_params)
        in_block = dict(updated.get(in_block_key, {}))

        for key in self.key_fields:
            next_value = cont_data.get(key)
            if next_value is None:
                return current_params, False

            if self.stop_condition == StopCondition.EMPTY_VALUE:
                if isinstance(next_value, str) and not next_value.strip():
                    return current_params, False
            elif self.stop_condition == StopCondition.ZERO_IDX:
                if key == "idx":
                    try:
                        if int(float(str(next_value))) == 0:
                            return current_params, False
                    except (ValueError, TypeError):
                        pass

            if key in in_block:
                in_block[key] = next_value

        updated[in_block_key] = in_block
        return updated, True


class TrSpec(BaseModel):
    code: str = Field(default="", description="TR code (from dict key)")
    name: str = Field(default="", alias="n")
    tr_class: TrClass = Field(..., alias="c")
    market: Market = Field(default=Market.ETC, alias="m")
    category: str = Field(default="", alias="cat")
    group: str = Field(default="", alias="grp")

    request_blocks: list[BlockSpec] = Field(default_factory=list, alias="rb")
    response_blocks: list[BlockSpec] = Field(default_factory=list, alias="pb")

    continuation: Optional[ContinuationSpec] = Field(default=None, alias="cont")

    example_request: dict[str, Any] = Field(default_factory=dict, alias="er")
    example_response: dict[str, Any] = Field(default_factory=dict, alias="ep")

    model_config = {"populate_by_name": True}

    @property
    def is_realtime(self) -> bool:
        return self.tr_class == TrClass.REALTIME

    @property
    def is_continuous(self) -> bool:
        return self.tr_class == TrClass.CONTINUOUS

    @property
    def is_query(self) -> bool:
        return self.tr_class == TrClass.QUERY

    def request_block(self, name: str | None = None) -> BlockSpec | None:
        if name:
            for b in self.request_blocks:
                if b.name == name:
                    return b
            return None
        for b in self.request_blocks:
            if "InBlock" in b.name:
                return b
        return self.request_blocks[0] if self.request_blocks else None

    def response_block(self, name: str | None = None) -> BlockSpec | None:
        if name:
            for b in self.response_blocks:
                if b.name == name:
                    return b
            return None
        return self.response_blocks[0] if self.response_blocks else None

    def get_field(self, name: str) -> FieldSpec | None:
        for block in self.request_blocks:
            found = block.get_field(name)
            if found:
                return found
        for block in self.response_blocks:
            found = block.get_field(name)
            if found:
                return found
        return None

    def build_request(self, values: dict[str, Any], strict: bool = False) -> dict[str, Any]:
        block = self.request_block()
        if not block:
            raise ValueError(f"TR '{self.code}' has no request block")

        known = block.field_names()
        unknown = set(values.keys()) - known
        if unknown:
            logger.warning("TR '%s': unknown fields ignored %s", self.code, unknown)

        result: dict[str, Any] = {}
        missing: list[str] = []

        for f in block.fields:
            if f.name not in values:
                if f.is_required:
                    if strict:
                        missing.append(f.name)
                    else:
                        logger.warning(
                            "TR '%s': required field '%s'(%s) omitted",
                            self.code, f.name, f.korean_name,
                        )
                continue

            value = values[f.name]
            try:
                value = self._coerce(f, value)
            except (ValueError, TypeError):
                raise TypeError(
                    f"'{f.name}'({f.korean_name}): "
                    f"'{values[f.name]}' cannot convert to {f.python_type.__name__}"
                )

            if isinstance(value, str) and f.max_length:
                if len(value) > f.max_length:
                    raise ValueError(
                        f"'{f.name}'({f.korean_name}): "
                        f"max {f.max_length} chars exceeded ({len(value)})"
                    )

            result[f.name] = value

        if missing:
            names = "', '".join(
                f"{n}({block.get_field(n).korean_name})" if block.get_field(n) else n
                for n in missing
            )
            raise ValueError(f"TR '{self.code}' required fields missing: '{names}'")

        return {block.name: result}

    def _coerce(self, field: FieldSpec, value: Any) -> Any:
        target = field.python_type
        if target == int and not isinstance(value, int):
            return int(float(str(value)))
        if target == float and not isinstance(value, float):
            return float(value)
        if target == str and not isinstance(value, str):
            return str(value)
        return value

    def parse_response(self, raw_body: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for block in self.response_blocks:
            block_data = raw_body.get(block.name)
            if block_data is None:
                continue

            if block.is_repeating:
                if isinstance(block_data, list):
                    parsed = []
                    for item in block_data:
                        parsed.append(
                            self._coerce_block(block, item)
                            if isinstance(item, dict)
                            else item
                        )
                    result[block.name] = parsed
                elif isinstance(block_data, dict):
                    result[block.name] = self._coerce_block(block, block_data)
            else:
                if isinstance(block_data, dict):
                    result[block.name] = self._coerce_block(block, block_data)
                else:
                    result[block.name] = block_data

        return result

    def parse_flat_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """실시간 데이터 등 flat dict를 필드 타입에 맞게 변환."""
        result: dict[str, Any] = {}
        for block in self.response_blocks:
            for f in block.fields:
                if f.name in data:
                    try:
                        result[f.name] = self._coerce(f, data[f.name])
                    except (ValueError, TypeError):
                        result[f.name] = data[f.name]
        return result

    def _coerce_block(self, block: BlockSpec, data: dict) -> dict:
        out: dict[str, Any] = {}
        for f in block.fields:
            if f.name in data:
                try:
                    out[f.name] = self._coerce(f, data[f.name])
                except (ValueError, TypeError):
                    out[f.name] = data[f.name]
        return out


class SpecRepository:
    def __init__(self, lazy: bool = True):
        self._specs: dict[str, TrSpec] | None = None
        if not lazy:
            self._load()

    def _load(self) -> dict[str, TrSpec]:
        if self._specs is not None:
            return self._specs

        import importlib.util, sys, os

        # _tr_specs.py를 패키지 컨텍스트 없이 직접 로드
        spec_path = os.path.join(os.path.dirname(__file__), "..", "_tr_specs.py")
        spec_path = os.path.normpath(spec_path)

        if not os.path.exists(spec_path):
            logger.warning("Run python lsbase/tools/generate_specs.py first")
            self._specs = {}
            return self._specs

        spec_loader = importlib.util.spec_from_file_location(
            "_tr_specs_loader", spec_path
        )
        if spec_loader is None:
            logger.warning("Failed to load _tr_specs.py")
            self._specs = {}
            return self._specs

        mod = importlib.util.module_from_spec(spec_loader)
        spec_loader.loader.exec_module(mod)
        SPECS = mod.SPECS

        self._specs = {}
        for code, raw in SPECS.items():
            try:
                spec = TrSpec.model_validate(raw)
                spec.code = code
                self._specs[code] = spec
            except Exception as e:
                logger.warning("TR '%s' parse error: %s", code, e)
        logger.info("SpecRepository: %d TRs loaded", len(self._specs))
        return self._specs

    def _find(self, code: str) -> TrSpec | None:
        specs = self._load()
        code_lower = code.strip().lower()
        for key, spec in specs.items():
            if key.lower() == code_lower:
                return spec
        return None

    def __getitem__(self, code: str) -> TrSpec:
        spec = self._find(code)
        if spec is None:
            raise KeyError(f"TR '{code}' not found")
        return spec

    def __contains__(self, code: str) -> bool:
        return self._find(code) is not None

    def __len__(self) -> int:
        return len(self._load())

    def __iter__(self):
        return iter(self._load().values())

    def get(self, code: str) -> Optional[TrSpec]:
        return self._find(code)

    def by_market(self, market: Market) -> list[TrSpec]:
        return [s for s in self._load().values() if s.market == market]

    def by_class(self, tr_class: TrClass) -> list[TrSpec]:
        return [s for s in self._load().values() if s.tr_class == tr_class]

    def search(self, query: str) -> list[TrSpec]:
        q = query.strip().lower()
        return [s for s in self._load().values() if q in s.code.lower() or q in s.name.lower()]


TrSpec.model_rebuild()
