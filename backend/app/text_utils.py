import re
import unicodedata


def clean_text(value):
    return " ".join(str(value or "").split())


def slugify(value):
    if not value:
        return ""

    value = str(value).replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_")


def is_valid_image_url(value):
    if not value:
        return False

    return str(value).strip().lower().startswith(("http://", "https://", "/images/"))
