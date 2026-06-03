import openpyxl

from .config import IMAGES_DIR, XLSX_PATH
from .constants import DEFAULT_ACTIVITIES
from .text_utils import is_valid_image_url, slugify


def load_xlsx():
    try:
        return openpyxl.load_workbook(XLSX_PATH, data_only=True)
    except Exception:
        return None


def load_media_assets(workbook):
    if not workbook or "media_assets" not in workbook.sheetnames:
        return {}

    media_assets = {}
    ws_media = workbook["media_assets"]

    for row in ws_media.iter_rows(min_row=2, values_only=True):
        media_id, dest_id, media_type, image_url, caption, alt_text, source_url = row[:7]

        if not dest_id or media_type != "image":
            continue

        media_assets[str(dest_id).strip()] = {
            "media_id": media_id,
            "image_url": str(image_url).strip() if is_valid_image_url(image_url) else "",
            "image_caption": caption,
            "image_alt": alt_text or caption,
            "image_source_url": source_url,
        }

    return media_assets


LOCAL_IMAGE_FALLBACK = {
    "TN005": "vuon_vo_nga.png",
    "TN007": "tinh_xa_ngoc_truyen.webp",
    "TN009": "linh_son_phuoc_trung_tu.webp",
    "TN010": "can_cu_dong_kim_quang.webp",
    "TN012": "dong_ba_co_quan_am_tu.png",
    "TN013": "tang_da_nut_doi.png",
    "TN014": "linh_son_tien_thach.webp",
    "TN016": "tuong_phat_nhap_niet_ban.png",
}


def _local_image_path(dest_code):
    fallback = LOCAL_IMAGE_FALLBACK.get(dest_code)
    if not fallback:
        return None
    candidate = IMAGES_DIR / fallback
    return f"/images/{candidate.name}" if candidate.exists() else None


def local_image_url_for(destination, media_asset):
    direct = _local_image_path(str(destination.get("dest_code", "")).strip())
    if direct:
        return direct
    if not IMAGES_DIR.exists():
        return ""
    candidates = [
        slugify(destination.get("name")),
        slugify(destination.get("dest_code")),
        slugify(media_asset.get("image_caption")),
        slugify(media_asset.get("image_alt")),
    ]
    image_files = [
        path
        for path in IMAGES_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]
    for candidate in candidates:
        if not candidate:
            continue
        for image_file in image_files:
            file_slug = slugify(image_file.stem)
            if candidate in file_slug or file_slug in candidate:
                return f"/images/{image_file.name}"
    return f"/images/{image_files[0].name}" if image_files else ""


def apply_media_assets(destinations, media_assets):
    for destination in destinations.values():
        media_asset = media_assets.get(
            str(destination.get("dest_code", "")).strip(), {}
        )
        external = media_asset.get("image_url")
        image_url = (
            local_image_url_for(destination, media_asset) or external or ""
        )
        destination["image_url"] = image_url
        destination["image_caption"] = (
            media_asset.get("image_caption") or destination.get("name")
        )
        destination["image_alt"] = media_asset.get("image_alt") or destination.get(
            "name"
        )
        destination["image_source_url"] = media_asset.get("image_source_url")
    return destinations


def fallback_destination():
    return {
        "id": 1,
        "dest_code": "TN001",
        "name": "Núi Bà Đen",
        "category": "Tâm linh / Cảnh quan",
        "location": "Tây Ninh, Việt Nam",
        "short_description": (
            "Khám phá biểu tượng du lịch sinh thái, tâm linh và cảnh quan "
            "nổi bật của Tây Ninh."
        ),
        "description_detail": (
            "Núi Bà Đen là điểm đến kết hợp du lịch tâm linh, cảnh quan "
            "và trải nghiệm cáp treo."
        ),
        "highlight": "Tượng Phật Bà; chóp đỉnh 986m; cáp treo",
        "best_time": "Sáng sớm hoặc chiều mát; đẹp nhất mùa khô 12-4",
        "estimated_duration": "1 ngày",
        "travel_type": "Tâm linh / Check-in",
        "difficulty_level": "Dễ",
        "transport": "Cáp treo tuyến Vân Sơn",
        "video_url": "https://example.com/video-nui-ba-den.mp4",
        "activities": DEFAULT_ACTIVITIES,
    }


def load_destinations(workbook):
    if not workbook or "destinations" not in workbook.sheetnames:
        return {1: fallback_destination()}

    destinations = {}
    ws = workbook["destinations"]
    rows = ws.iter_rows(min_row=2, values_only=True)

    for idx, row in enumerate(rows, start=1):
        if not row[0]:
            continue

        destinations[idx] = {
            "id": idx,
            "dest_code": row[0],
            "name": row[1],
            "category": row[2],
            "location": row[3],
            "short_description": row[4],
            "description_detail": row[6] or row[4],
            "highlight": row[6],
            "best_time": row[7],
            "estimated_duration": row[8],
            "travel_type": row[9],
            "difficulty_level": row[10],
            "transport": row[11],
            "video_url": "https://example.com/video-nui-ba-den.mp4",
            "activities": DEFAULT_ACTIVITIES,
        }

    return destinations or {1: fallback_destination()}


def load_faqs(workbook):
    if not workbook or "faq" not in workbook.sheetnames:
        return []

    faqs = []
    ws_faq = workbook["faq"]

    for row in ws_faq.iter_rows(min_row=2, values_only=True):
        if row[0]:
            faqs.append(
                {
                    "faq_id": row[0],
                    "topic": row[1],
                    "question": row[2],
                    "answer": row[3],
                    "intent": row[4],
                    "source_url": row[5],
                }
            )

    return faqs


def _load_sheet_records(workbook, sheet_name, required_field):
    if not workbook or sheet_name not in workbook.sheetnames:
        return []

    ws = workbook[sheet_name]
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
    records = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        record = {
            str(header): value
            for header, value in zip(headers, row)
            if header and value is not None
        }

        if record.get(required_field):
            records.append(record)

    return records


def load_services_pricing(workbook):
    return _load_sheet_records(workbook, "services_pricing", "service_id")


def load_activities(workbook):
    return _load_sheet_records(workbook, "activities", "activity_id")


def load_knowledge_base(workbook):
    if not workbook or "knowledge_base" not in workbook.sheetnames:
        return []

    knowledge_base = []
    ws_kb = workbook["knowledge_base"]

    for row in ws_kb.iter_rows(min_row=2, values_only=True):
        if row[0]:
            knowledge_base.append(
                {
                    "kb_id": row[0],
                    "topic": row[1],
                    "title": row[2],
                    "content": row[3],
                    "keywords": row[4],
                    "source_url": row[5],
                }
            )

    return knowledge_base


WORKBOOK = load_xlsx()
MEDIA_ASSETS = load_media_assets(WORKBOOK)
DESTINATIONS = apply_media_assets(load_destinations(WORKBOOK), MEDIA_ASSETS)
FAQ_LIST = load_faqs(WORKBOOK)
SERVICES_PRICING = load_services_pricing(WORKBOOK)
ACTIVITIES = load_activities(WORKBOOK)
KB_LIST = load_knowledge_base(WORKBOOK)
