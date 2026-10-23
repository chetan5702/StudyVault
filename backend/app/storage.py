import uuid
import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from fastapi import HTTPException, UploadFile
from PIL import Image
from pypdf import PdfReader

from app.config import get_settings

settings = get_settings()

CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
WORD_NAMESPACES = {
    "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "http://purl.oclc.org/ooxml/wordprocessingml/main",
}
WORD_DOCUMENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def validate_docx(archive: zipfile.ZipFile) -> None:
    entries = archive.infolist()
    if sum(item.file_size for item in entries) > settings.max_upload_size_bytes * 5:
        raise ValueError("Archive too large")
    names = set(archive.namelist())
    if (
        len(names) != len(entries)
        or not {"[Content_Types].xml", "word/document.xml"} <= names
        or any("vbaproject" in name.lower() for name in names)
    ):
        raise ValueError("Invalid Word document")
    document = ElementTree.fromstring(archive.read("word/document.xml"))
    if document.tag not in {f"{{{namespace}}}document" for namespace in WORD_NAMESPACES}:
        raise ValueError("Invalid Word document namespace")
    types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
    if types.tag != f"{{{CONTENT_TYPES_NS}}}Types":
        raise ValueError("Invalid package content types")
    main_types = []
    for item in types:
        content_type = item.get("ContentType", "")
        if any(marker in content_type.lower() for marker in ("macroenabled", "vbaproject")):
            raise ValueError("Macro-enabled documents are not supported")
        if (
            item.tag == f"{{{CONTENT_TYPES_NS}}}Override"
            and item.get("PartName") == "/word/document.xml"
        ):
            main_types.append(content_type)
    if main_types != [WORD_DOCUMENT_TYPE]:
        raise ValueError("Missing or invalid Word document content type")
    # Macro parts may have arbitrary filenames; their relationship type still
    # identifies them even if the package omits their declared content type.
    for name in names:
        if name.lower().endswith(".rels"):
            relationships = ElementTree.fromstring(archive.read(name))
            if any("vbaproject" in item.get("Type", "").lower() for item in relationships):
                raise ValueError("Macro-enabled documents are not supported")


def ensure_storage() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def detect_type(path: Path) -> tuple[str, str]:
    with path.open("rb") as stream:
        signature = stream.read(8)
    try:
        if signature.startswith(b"%PDF-"):
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted or not len(reader.pages):
                raise ValueError("Encrypted or empty PDF")
            return "application/pdf", ".pdf"
        if signature.startswith(b"\x89PNG\r\n\x1a\n") or signature.startswith(b"\xff\xd8\xff"):
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(path) as image:
                    image_format = image.format
                    if image_format not in ("PNG", "JPEG"):
                        raise ValueError("Unsupported image")
                    image.verify()
                # JPEG verify() only checks its headers. Decode the image too
                # so truncated/corrupt pixel data cannot pass as a valid upload.
                with Image.open(path) as image:
                    image.load()
            return ("image/png", ".png") if image_format == "PNG" else ("image/jpeg", ".jpg")
        if signature.startswith(b"PK"):
            with zipfile.ZipFile(path) as archive:
                validate_docx(archive)
                return (
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".docx",
                )
    except Exception as exc:
        raise HTTPException(400, "Invalid file contents") from exc
    raise HTTPException(400, "Unsupported file contents; use PDF, PNG, JPEG or DOCX")


def save_upload(file: UploadFile) -> tuple[Path, str, str, int]:
    path = ensure_storage() / f"{uuid.uuid4().hex}.part"
    size = 0
    try:
        with path.open("xb") as sink:
            while chunk := file.file.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_size_bytes:
                    raise HTTPException(413, "File exceeds upload limit")
                sink.write(chunk)
        if not size:
            raise HTTPException(400, "File is empty")
        mime, extension = detect_type(path)
        final = path.with_suffix(extension)
        path.rename(final)
        return final, final.name, mime, size
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def get_file_path(storage_key: str) -> Path:
    root = ensure_storage()
    legacy = Path(storage_key).resolve()
    candidate = (legacy if legacy.is_relative_to(root) else root / Path(storage_key).name).resolve()
    if not candidate.is_relative_to(root):
        raise HTTPException(404, "Stored file not found")
    return candidate
