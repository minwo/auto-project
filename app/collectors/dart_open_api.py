from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
from xml.etree import ElementTree


CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DISCLOSURE_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_REPORT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo="


DISCLOSURE_CODE_CLASSIFICATION: dict[str, tuple[str, bool]] = {
    "A001": ("periodic", False),
    "A002": ("periodic", False),
    "A003": ("periodic", False),
    "A004": ("periodic", False),
    "A005": ("periodic", False),
    "B001": ("material", True),
    "B002": ("capital_event", True),
    "B003": ("corporate_action", True),
    "B004": ("dilution", True),
    "B005": ("buyback", True),
    "B006": ("trading_risk", True),
    "C001": ("contract", True),
    "C002": ("earnings", True),
    "C003": ("capex", True),
    "C004": ("approval", True),
    "D001": ("ownership", True),
    "E001": ("management_risk", True),
    "F001": ("ownership", True),
    "G001": ("disclosure", False),
    "H001": ("policy", True),
    "I001": ("dilution", True),
}


DISCLOSURE_KEYWORD_RULES: list[tuple[str, bool, list[str]]] = [
    ("contract", True, ["contract", "supply", "sales agreement", "purchase order", "단일판매", "공급계약", "수주", "납품", "체결"]),
    ("earnings", True, ["quarterly", "semiannual", "annual", "business report", "earnings", "잠정실적", "영업실적", "매출액", "영업이익", "손익구조", "결산"]),
    ("dilution", True, ["capital increase", "bond", "convertible", "warrant", "cb", "bw", "유상증자", "전환사채", "신주인수권", "교환사채", "사채권"]),
    ("buyback", True, ["treasury stock", "buyback", "자기주식", "자사주", "소각", "신탁계약"]),
    ("ownership", True, ["major shareholder", "최대주주", "최대주주변경"]),
    ("trading_risk", True, ["listing", "delisting", "trading suspension", "거래정지", "상장폐지", "불성실공시", "관리종목", "투자주의", "투자경고", "투자위험"]),
    ("approval", True, ["approval", "license", "fda", "clinical", "품목허가", "승인", "인증", "임상", "허가신청"]),
    ("capex", True, ["facility investment", "capacity expansion", "시설투자", "신규시설", "공장", "증설", "투자결정"]),
    ("capital_event", True, ["무상증자", "액면분할", "주식분할"]),
    ("corporate_action", True, ["합병", "분할", "영업양수", "영업양도", "인수", "m&a"]),
    ("management_risk", True, ["소송", "횡령", "배임", "감사의견", "회생", "파산"]),
    ("dividend", True, ["배당", "현금ㆍ현물배당", "중간배당", "분기배당", "dividend"]),
]


@dataclass(slots=True)
class DartCorpCodeRecord:
    corp_code: str
    corp_name: str
    stock_code: str | None
    modify_date: str | None = None


@dataclass(slots=True)
class DartDisclosureRecord:
    trade_date: date
    code: str
    dart_corp_code: str
    receipt_no: str
    report_name: str
    report_type: str | None
    disclosed_at: date
    url: str
    is_material: bool
    material_tag: str | None


def _text(element: ElementTree.Element, name: str) -> str | None:
    child = element.find(name)
    if child is None or child.text is None:
        return None
    value = child.text.strip()
    return value or None


def parse_corp_code_zip(payload: bytes) -> list[DartCorpCodeRecord]:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
        if not xml_names:
            raise RuntimeError("DART corpCode response does not contain an XML file.")
        xml_payload = archive.read(xml_names[0])

    root = ElementTree.fromstring(xml_payload)
    records: list[DartCorpCodeRecord] = []
    for item in root.findall("list"):
        corp_code = _text(item, "corp_code")
        corp_name = _text(item, "corp_name")
        stock_code = _text(item, "stock_code")
        if not corp_code or not corp_name:
            continue
        records.append(
            DartCorpCodeRecord(
                corp_code=corp_code,
                corp_name=corp_name,
                stock_code=stock_code if stock_code and stock_code.strip() else None,
                modify_date=_text(item, "modify_date"),
            )
        )
    return records


def fetch_corp_code_records(
    *,
    api_key: str,
    timeout: int = 30,
) -> list[DartCorpCodeRecord]:
    request_url = f"{CORP_CODE_URL}?{urlencode({'crtfc_key': api_key})}"
    with urlopen(request_url, timeout=timeout) as response:
        payload = response.read()
    return parse_corp_code_zip(payload)


def _classify_report(report_name: str, *classification_codes: str | None) -> tuple[str | None, bool]:
    for code in classification_codes:
        normalized_code = (code or "").strip().upper()
        if not normalized_code:
            continue
        if normalized_code in DISCLOSURE_CODE_CLASSIFICATION:
            return DISCLOSURE_CODE_CLASSIFICATION[normalized_code]

    haystack = report_name.lower()
    for tag, is_material, keywords in DISCLOSURE_KEYWORD_RULES:
        if any(keyword.lower() in haystack for keyword in keywords):
            return tag, is_material

    if "주요사항보고" in report_name:
        return "material", True
    return None, False


def parse_disclosure_list_payload(payload: dict[str, Any], *, trade_date: date) -> list[DartDisclosureRecord]:
    status = payload.get("status")
    if status == "013":
        return []
    if status not in (None, "000"):
        raise RuntimeError(payload.get("message") or f"DART disclosure request failed: status={status}")

    records: list[DartDisclosureRecord] = []
    for item in payload.get("list") or []:
        stock_code = str(item.get("stock_code") or "").strip()
        receipt_no = str(item.get("rcept_no") or "").strip()
        report_name = str(item.get("report_nm") or "").strip()
        corp_code = str(item.get("corp_code") or "").strip()
        receipt_date = str(item.get("rcept_dt") or "").strip()
        if not stock_code or not receipt_no or not report_name or not corp_code or len(receipt_date) != 8:
            continue

        material_tag, is_material = _classify_report(
            report_name,
            item.get("report_cd"),
            item.get("pblntf_detail_ty"),
            item.get("pblntf_ty"),
        )
        disclosed_at = date.fromisoformat(f"{receipt_date[0:4]}-{receipt_date[4:6]}-{receipt_date[6:8]}")
        records.append(
            DartDisclosureRecord(
                trade_date=trade_date,
                code=stock_code,
                dart_corp_code=corp_code,
                receipt_no=receipt_no,
                report_name=report_name,
                report_type=material_tag,
                disclosed_at=disclosed_at,
                url=f"{DART_REPORT_URL}{receipt_no}",
                is_material=is_material,
                material_tag=material_tag,
            )
        )
    return records


def fetch_disclosure_records(
    *,
    api_key: str,
    trade_date: date,
    page_count: int = 100,
    timeout: int = 30,
) -> list[DartDisclosureRecord]:
    ymd = trade_date.strftime("%Y%m%d")
    params = {
        "crtfc_key": api_key,
        "bgn_de": ymd,
        "end_de": ymd,
        "page_count": page_count,
    }
    request_url = f"{DISCLOSURE_LIST_URL}?{urlencode(params)}"
    with urlopen(request_url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_disclosure_list_payload(payload, trade_date=trade_date)
