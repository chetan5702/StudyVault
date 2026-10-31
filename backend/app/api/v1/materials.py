from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import and_, case, delete, func, or_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import ClassMember, Material, Subject, Unit, User, UserStorageUsage
from app.object_storage import delete_stored_file, download_stored_file, upload_validated_file
from app.schemas import MaterialCreate, MaterialOut
from app.storage import save_upload

router = APIRouter(tags=["materials"])


@router.get("/materials/config")
def material_configuration(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, int]:
    settings = get_settings()
    used_bytes = owned_storage_bytes(db, current_user.id)
    return {
        "max_upload_size_bytes": settings.max_upload_size_bytes,
        "max_user_storage_bytes": settings.max_user_storage_bytes,
        "used_storage_bytes": used_bytes,
        "remaining_storage_bytes": max(0, settings.max_user_storage_bytes - used_bytes),
    }


def owned_storage_bytes(db: Session, user_id: str) -> int:
    stored = (
        db.query(
            func.coalesce(
                func.sum(case((Material.size_bytes > 0, Material.size_bytes), else_=0)),
                0,
            )
        )
        .filter(Material.user_id == user_id)
        .scalar()
    )
    return int(stored or 0)


def ensure_storage_usage_row(db: Session, user_id: str) -> None:
    values = {
        "user_id": user_id,
        "used_bytes": owned_storage_bytes(db, user_id),
        "updated_at": func.now(),
    }
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        db.execute(sqlite_insert(UserStorageUsage).values(**values).on_conflict_do_nothing())
    elif dialect == "postgresql":
        db.execute(postgresql_insert(UserStorageUsage).values(**values).on_conflict_do_nothing())
    elif db.get(UserStorageUsage, user_id) is None:
        db.add(UserStorageUsage(**values))
        db.flush()


def reserve_storage(db: Session, user_id: str, size_bytes: int) -> None:
    ensure_storage_usage_row(db, user_id)
    settings = get_settings()
    result = db.execute(
        update(UserStorageUsage)
        .where(
            UserStorageUsage.user_id == user_id,
            UserStorageUsage.used_bytes + size_bytes <= settings.max_user_storage_bytes,
        )
        .values(
            used_bytes=UserStorageUsage.used_bytes + size_bytes,
            updated_at=func.now(),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(413, "Storage quota exceeded")


def release_storage(db: Session, user_id: str, size_bytes: int) -> None:
    released = max(0, size_bytes)
    result = db.execute(
        update(UserStorageUsage)
        .where(UserStorageUsage.user_id == user_id)
        .values(
            used_bytes=case(
                (UserStorageUsage.used_bytes >= released, UserStorageUsage.used_bytes - released),
                else_=0,
            ),
            updated_at=func.now(),
        )
    )
    if result.rowcount != 1:
        # The deleted material is already absent from owned_storage_bytes(), so
        # reconstruct a missing legacy counter without subtracting it twice.
        ensure_storage_usage_row(db, user_id)


def member(db, user_id, group_id):
    return db.query(ClassMember).filter_by(user_id=user_id, group_id=group_id).first() is not None


def accessible(db, user, material_id):
    material = db.get(Material, material_id)
    if not material or not (
        material.user_id == user.id
        or (
            material.visibility == "group"
            and material.group_id
            and member(db, user.id, material.group_id)
        )
    ):
        raise HTTPException(404, "Material not found")
    return material


@router.get("/materials", response_model=list[MaterialOut])
def list_materials(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search: str | None = None,
    category: str | None = None,
    subject_id: str | None = None,
):
    groups = db.query(ClassMember.group_id).filter(ClassMember.user_id == current_user.id)
    query = db.query(Material).filter(
        or_(
            Material.user_id == current_user.id,
            and_(Material.visibility == "group", Material.group_id.in_(groups)),
        )
    )
    if search:
        query = query.filter(
            or_(
                Material.title.ilike(f"%{search}%"),
                Material.file_name.ilike(f"%{search}%"),
            )
        )
    if category:
        query = query.filter(Material.category == category)
    if subject_id:
        query = query.filter(Material.subject_id == subject_id)
    return query.order_by(Material.created_at.desc()).all()


@router.post("/materials/upload", response_model=MaterialOut, status_code=201)
def upload_material(
    file: UploadFile = File(...),
    payload: MaterialCreate = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not db.query(Subject).filter_by(id=payload.subject_id, user_id=current_user.id).first():
        raise HTTPException(404, "Subject not found")
    if (
        payload.unit_id
        and not db.query(Unit).filter_by(id=payload.unit_id, subject_id=payload.subject_id).first()
    ):
        raise HTTPException(400, "Unit does not belong to subject")
    if payload.group_id and not member(db, current_user.id, payload.group_id):
        raise HTTPException(403, "Group membership required")
    if payload.visibility == "group" and not payload.group_id:
        raise HTTPException(400, "Shared materials require a group")
    if payload.visibility == "private" and payload.group_id:
        raise HTTPException(400, "Private materials cannot specify a group")
    path, key, mime, size = save_upload(file)
    filename = PurePosixPath((file.filename or key).replace("\\", "/")).name
    filename = "".join(c for c in filename if ord(c) >= 32)[:200] or key
    try:
        reserve_storage(db, current_user.id, size)
        persisted_key = upload_validated_file(
            path, f"{current_user.id}/{key}", mime
        ) if get_settings().storage_backend == "s3" else key
        material = Material(
            user_id=current_user.id,
            **payload.model_dump(),
            file_name=filename,
            storage_key=persisted_key,
            mime_type=mime,
            size_bytes=size,
        )
        db.add(material)
        db.flush()
        db.refresh(material)
        db.commit()
        if persisted_key.startswith('s3:'):
            path.unlink(missing_ok=True)
        return material
    except BaseException:
        db.rollback()
        path.unlink(missing_ok=True)
        if 'persisted_key' in locals() and persisted_key.startswith('s3:'):
            delete_stored_file(persisted_key)
        raise


@router.get("/materials/{material_id}", response_model=MaterialOut)
def get_material(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return accessible(db, current_user, material_id)


@router.get("/materials/{material_id}/download")
def download_material(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    material = accessible(db, current_user, material_id)
    return download_stored_file(material.storage_key, material.file_name, material.mime_type)

@router.delete("/materials/{material_id}")
def delete_material(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        deleted = db.execute(
            delete(Material)
            .where(Material.id == material_id, Material.user_id == current_user.id)
            .returning(Material.storage_key, Material.size_bytes)
        ).one_or_none()
        if deleted is None:
            raise HTTPException(404, "Material not found")

        storage_key, size_bytes = deleted
        release_storage(db, current_user.id, int(size_bytes or 0))
        db.commit()
    except BaseException:
        db.rollback()
        raise

    delete_stored_file(storage_key)
    return {"status": "deleted"}
