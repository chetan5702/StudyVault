import zipfile
from io import BytesIO

import pytest
from PIL import Image

from app.storage import ensure_storage
from tests.test_workflow import P, subject, upload


def docx(macro=False, content_types=None, document_xml=None, extra_parts=None):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            content_types
            if content_types is not None
            else '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml" /></Types>',
        )
        archive.writestr(
            "word/document.xml",
            document_xml
            if document_xml is not None
            else '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body /></w:document>',
        )
        if macro:
            archive.writestr("word/vbaProject.bin", b"macro")
        for name, contents in (extra_parts or {}).items():
            archive.writestr(name, contents)
    return stream.getvalue()


def test_valid_docx(client, student):
    response = upload(client, student, subject(client, student), docx())
    assert response.status_code == 201
    assert (
        response.json()["mime_type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_macro_docx_rejected(client, student):
    assert upload(client, student, subject(client, student), docx(macro=True)).status_code == 400
    assert list(ensure_storage().iterdir()) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"content_types": "<nothing/>"},
        {
            "content_types": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
        },
        {"document_xml": '<x:document xmlns:x="urn:bogus"/>'},
        {"extra_parts": {"word/VBAPROJECT.BIN": b"macro"}},
        {
            "content_types": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/hidden.bin" ContentType="application/vnd.ms-office.vbaProject"/></Types>',
            "extra_parts": {"word/hidden.bin": b"macro"},
        },
        {
            "extra_parts": {
                "word/hidden.bin": b"macro",
                "word/_rels/document.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="macro" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="hidden.bin"/></Relationships>',
            },
        },
    ],
    ids=[
        "wrong-types-root",
        "missing-main-type",
        "wrong-document-namespace",
        "uppercase-macro",
        "renamed-macro-type",
        "renamed-macro-relationship",
    ],
)
def test_invalid_docx_package_rejected(client, student, changes):
    response = upload(client, student, subject(client, student), docx(**changes))
    assert response.status_code == 400
    assert client.get(P + "/materials", headers=student).json() == []
    assert list(ensure_storage().iterdir()) == []


@pytest.mark.parametrize("missing_bytes", [2, 100])
def test_truncated_jpeg_rejected(client, student, missing_bytes):
    stream = BytesIO()
    Image.new("RGB", (100, 100)).save(stream, format="JPEG")
    response = upload(client, student, subject(client, student), stream.getvalue()[:-missing_bytes])
    assert response.status_code == 400
    assert client.get(P + "/materials", headers=student).json() == []
    assert list(ensure_storage().iterdir()) == []


def test_image_decompression_bomb_rejected(client, student, monkeypatch):
    stream = BytesIO()
    Image.new("RGB", (10, 10)).save(stream, format="PNG")
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 90)
    response = upload(client, student, subject(client, student), stream.getvalue())
    assert response.status_code == 400
    assert client.get(P + "/materials", headers=student).json() == []
    assert list(ensure_storage().iterdir()) == []


def test_inactive_account_denied(client, student):
    from app.database import SessionLocal
    from app.models import User

    me = client.get(P + "/auth/me", headers=student).json()
    with SessionLocal() as db:
        db.get(User, me["id"]).is_active = False
        db.commit()
    assert client.get(P + "/subjects", headers=student).status_code == 401
    assert (
        client.post(
            P + "/auth/login", json={"email": "one@example.com", "password": "Password123!"}
        ).status_code
        == 401
    )


def test_startup_does_not_seed_accounts(client):
    from app.database import SessionLocal
    from app.models import College, User

    with SessionLocal() as db:
        assert db.query(User).count() == 0
        assert db.query(College).count() == 0
