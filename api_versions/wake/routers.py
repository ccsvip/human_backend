from fastapi import APIRouter, HTTPException, Request, Depends
from .models import WakeWord
from .schema import WakeWordCreateSchema, WakeWordSchema
from api_versions.logs.utils import record_operation_log
from api_versions.auth.routers import get_current_user
from api_versions.v2.models import User

router = APIRouter()


@router.get("/", response_model=list[WakeWordSchema])
async def list_wake_words():
    return await WakeWord.all()


@router.post("/", response_model=WakeWordSchema)
async def create_wakeword(
    request: Request,
    data: WakeWordCreateSchema,
    current_user: User = Depends(get_current_user)
):
    obj = await WakeWord.create(**data.model_dump())

    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="CREATE",
        operation_content=f"创建唤醒词: {obj.word}",
        target_type="wakeword",
        target_id=obj.id,
        user=current_user,
        details={"word": obj.word, "description": obj.description}
    )

    return obj


@router.put("/{id}", response_model=WakeWordSchema)
async def update_wakeword(
    id: int,
    request: Request,
    data: WakeWordCreateSchema,
    current_user: User = Depends(get_current_user)
):
    obj = await WakeWord.get_or_none(id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="唤醒词不存在")

    # 保存原始数据用于日志
    old_word = obj.word
    old_description = obj.description

    obj.word = data.word
    obj.description = data.description
    await obj.save()

    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="UPDATE",
        operation_content=f"更新唤醒词: {obj.word}",
        target_type="wakeword",
        target_id=obj.id,
        user=current_user,
        details={
            "old_word": old_word,
            "new_word": obj.word,
            "old_description": old_description,
            "new_description": obj.description
        }
    )

    return obj


@router.delete("/{id}")
async def delete_wakeword(
    id: int,
    request: Request,
    current_user: User = Depends(get_current_user)
):
    obj = await WakeWord.get_or_none(id=id)
    if not obj:
        raise HTTPException(status_code=404, detail="唤醒词不存在")

    # 保存删除前的数据用于日志
    deleted_word = obj.word
    deleted_description = obj.description

    await obj.delete()

    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="DELETE",
        operation_content=f"删除唤醒词: {deleted_word}",
        target_type="wakeword",
        target_id=id,
        user=current_user,
        details={"word": deleted_word, "description": deleted_description}
    )

    return {"ok": True}

