"""TrSpec, FieldSpec, BlockSpec, ContinuationSpec 단위 테스트 (네트워크 불필요)"""
import sys
sys.path.insert(0, '.')

import pytest
from lsbase.core.spec_models import (
    FieldSpec, BlockSpec, ContinuationSpec, TrSpec,
    TrClass, Market, StopCondition,
)


class TestFieldSpec:
    def test_python_type_str(self):
        f = FieldSpec(n="shcode", t="A0001", l="6")
        assert f.python_type == str

    def test_python_type_int(self):
        f = FieldSpec(n="price", t="A0003", l="8")
        assert f.python_type == int
        f = FieldSpec(n="volume", t="A0004", l="12")
        assert f.python_type == int

    def test_python_type_float_by_length(self):
        f = FieldSpec(n="diff", t="A0001", l="6.2")
        assert f.python_type == float

    def test_python_type_float_by_code(self):
        f = FieldSpec(n="diff", t="A0005")
        assert f.python_type == float

    def test_python_type_str_fallback(self):
        f = FieldSpec(n="hname", t="A0001")
        assert f.python_type == str

    def test_max_length(self):
        f = FieldSpec(n="shcode", l="6")
        assert f.max_length == 6
        f = FieldSpec(n="price", l="12.2")
        assert f.max_length == 12
        f = FieldSpec(n="empty")
        assert f.max_length is None

    def test_required(self):
        f = FieldSpec(n="req", r=True)
        assert f.is_required is True
        f = FieldSpec(n="opt", r=False)
        assert f.is_required is False


class TestBlockSpec:
    @pytest.fixture
    def block(self):
        return BlockSpec(
            n="t1102InBlock",
            f=[
                FieldSpec(n="shcode", k="단축코드", r=True),
                FieldSpec(n="exchgubun", k="거래소구분코드", r=True),
            ],
        )

    def test_field_names(self, block):
        assert block.field_names() == {"shcode", "exchgubun"}

    def test_get_field(self, block):
        f = block.get_field("shcode")
        assert f is not None
        assert f.korean_name == "단축코드"
        assert block.get_field("nonexistent") is None

    def test_required_fields(self, block):
        req = block.required_fields()
        assert len(req) == 2


class TestTrSpec:
    RAW_SAMPLE = {
        "n": "주식현재가(시세)조회",
        "c": "query",
        "m": "stock",
        "cat": "주식",
        "grp": "[주식] 시세",
        "rb": [{
            "n": "t1102InBlock", "r": False, "f": [
                {"n": "shcode", "k": "단축코드", "t": "str", "l": "6", "r": True},
                {"n": "exchgubun", "k": "거래소구분코드", "t": "str", "l": "1", "r": True},
            ],
        }],
        "pb": [{
            "n": "t1102OutBlock", "r": False, "f": [
                {"n": "hname", "k": "한글명", "t": "str", "l": "20", "r": False},
                {"n": "price", "k": "현재가", "t": "int", "l": "8", "r": False},
                {"n": "diff", "k": "등락율", "t": "float", "l": "6.2", "r": False},
                {"n": "volume", "k": "거래량", "t": "int", "l": "12", "r": False},
            ],
        }],
        "er": {},
        "ep": {},
    }

    @pytest.fixture
    def tr(self):
        s = TrSpec.model_validate(self.RAW_SAMPLE)
        s.code = "t1102"
        return s

    def test_build_request_basic(self, tr):
        packet = tr.build_request({"shcode": "005930"})
        assert packet == {"t1102InBlock": {"shcode": "005930"}}

    def test_build_request_type_coercion(self, tr):
        tr2 = TrSpec.model_validate({
            **self.RAW_SAMPLE,
            "rb": [{"n": "t1305InBlock", "r": False, "f": [
                {"n": "idx", "k": "IDX", "t": "int", "l": "4", "r": True},
                {"n": "cnt", "k": "건수", "t": "int", "l": "4", "r": True},
            ]}],
        })
        tr2.code = "t1305"
        packet = tr2.build_request({"idx": "0", "cnt": "100"})
        assert packet == {"t1305InBlock": {"idx": 0, "cnt": 100}}
        assert isinstance(packet["t1305InBlock"]["idx"], int)

    def test_build_request_strict_mode(self, tr):
        with pytest.raises(ValueError, match="required fields missing"):
            tr.build_request({}, strict=True)

    def test_build_request_lenient_mode(self, tr):
        packet = tr.build_request({})
        assert "shcode" not in packet["t1102InBlock"]

    def test_build_request_unknown_field_lenient(self, tr):
        packet = tr.build_request({"shcode": "005930", "unknown": "x"})
        assert "unknown" not in packet["t1102InBlock"]

    def test_build_request_unknown_field_strict(self, tr):
        with pytest.raises(ValueError, match="unknown fields"):
            tr.build_request({"shcode": "005930", "unknown": "x"}, strict=True)

    def test_build_request_length_validation(self, tr):
        with pytest.raises(ValueError, match="max 1 chars"):
            tr.build_request({"shcode": "005930", "exchgubun": "KRX"}, strict=True)

    def test_parse_response(self, tr):
        parsed = tr.parse_response({
            "rsp_cd": "00000",
            "rsp_msg": "success",
            "t1102OutBlock": {
                "hname": "삼성전자", "price": "71700", "diff": "-1.93", "volume": "123456",
            },
        })
        ob = parsed["t1102OutBlock"]
        assert ob["hname"] == "삼성전자"
        assert ob["price"] == 71700
        assert isinstance(ob["price"], int)
        assert ob["diff"] == -1.93
        assert isinstance(ob["diff"], float)
        assert ob["volume"] == 123456

    def test_parse_response_with_meta(self, tr):
        parsed, meta = tr._parse_response_with_meta({
            "rsp_cd": "00000",
            "rsp_msg": "success",
            "t1102OutBlock": {"hname": "삼성전자", "price": "71700"},
            "extra_block": {},
        })
        assert "extra_block" in str(meta["unknown_fields"])
        assert meta["missing_blocks"] == []

    def test_properties(self, tr):
        assert tr.is_query is True
        assert tr.is_realtime is False
        assert tr.is_continuous is False

    def test_request_block(self, tr):
        block = tr.request_block()
        assert block is not None
        assert block.name == "t1102InBlock"
        assert tr.request_block("nonexistent") is None

    def test_get_field(self, tr):
        assert tr.get_field("shcode") is not None
        assert tr.get_field("price") is not None
        assert tr.get_field("nonexistent") is None


class TestContinuationSpec:
    @pytest.fixture
    def cont(self):
        return ContinuationSpec(
            db="t1444OutBlock1",
            cb="t1444OutBlock",
            kf=["idx"],
            stop="zero_idx",
        )

    def test_extract_next_params_zero_idx(self, cont):
        params = {"t1444InBlock": {"upcode": "001", "idx": 0}}
        body = {
            "rsp_cd": "00000",
            "t1444OutBlock": {"idx": 5},
            "t1444OutBlock1": [{"hname": "삼성전자"}],
        }
        updated, should_continue = cont.extract_next_params(body, params, "t1444InBlock")
        assert should_continue is True
        assert updated["t1444InBlock"]["idx"] == 5

    def test_extract_next_params_stop(self, cont):
        params = {"t1444InBlock": {"upcode": "001", "idx": 5}}
        body = {
            "rsp_cd": "00000",
            "t1444OutBlock": {"idx": 0},
            "t1444OutBlock1": [{"hname": "삼성전자"}],
        }
        _, should_continue = cont.extract_next_params(body, params, "t1444InBlock")
        assert should_continue is False

    def test_extract_next_params_empty_value(self):
        cont = ContinuationSpec(
            db="t8412OutBlock1",
            cb="t8412OutBlock",
            kf=["cts_date", "cts_time"],
            stop="empty_value",
        )
        params = {"t8412InBlock": {"shcode": "005930", "cts_date": "20240101", "cts_time": "100000"}}
        body = {
            "rsp_cd": "00000",
            "t8412OutBlock": {"cts_date": "20240102", "cts_time": ""},
            "t8412OutBlock1": [{"date": "20240102"}],
        }
        _, should_continue = cont.extract_next_params(body, params, "t8412InBlock")
        assert should_continue is False

    def test_extract_next_params_missing_key(self, cont):
        params = {"t1444InBlock": {"idx": 5}}
        body = {"rsp_cd": "00000", "t1444OutBlock": {}}
        _, should_continue = cont.extract_next_params(body, params, "t1444InBlock")
        assert should_continue is False
