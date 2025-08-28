from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Request, Depends
from api_versions.v2.models import ModelItem, User
from api_versions.v2.schema import ModelCreateSchema, ModelUpdateSchema, Model_Pydantic
import os
import uuid
from pathlib import Path
from api_versions.logs.utils import record_operation_log
from api_versions.auth.routers import get_current_user

router = APIRouter()

def format_file_size(file_size: int) -> str:
    """
    格式化文件大小为可读字符串
    """
    if not file_size:
        return "未知"
    
    if file_size < 1024:
        return f"{file_size}B"
    elif file_size < 1024 * 1024:
        return f"{file_size / 1024:.1f}KB"
    elif file_size < 1024 * 1024 * 1024:
        return f"{file_size / (1024 * 1024):.1f}MB"
    else:
        return f"{file_size / (1024 * 1024 * 1024):.1f}GB"

def get_full_url(request: Request, local_path: str) -> str:
    """将本地路径转换为完整的可访问URL"""
    if not local_path:
        return None
    
    # 将路径标准化为正斜杠
    normalized_path = local_path.replace('\\', '/')
    
    # 如果路径以static/开头，去掉static/前缀，因为FastAPI挂载在/static下
    if normalized_path.startswith('static/'):
        file_path = normalized_path[7:]  # 去掉"static/"前缀
    else:
        file_path = normalized_path
    
    # 使用FastAPI的url_for生成完整URL
    return str(request.url_for('audio_files', path=file_path))

@router.post("/models", status_code=status.HTTP_201_CREATED, summary="创建模型")
async def create_model(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    category: str = Form(...),
    orientation: str = Form(None),
    url: str = Form(None),
    file_size: int = Form(None),
    is_show: bool = Form(True),
    model_file: UploadFile = File(None),
    thumbnail_file: UploadFile = File(None),
    current_user: User = Depends(get_current_user)
):
    try:
        # 处理本地模型文件上传
        local_path = None
        calculated_file_size = None
        if model_file:
            # 验证文件格式
            if not model_file.filename.lower().endswith('.zip'):
                raise HTTPException(status_code=400, detail="模型文件必须是.zip格式")
            
            # 确保模型目录存在
            models_dir = Path("static/models")
            models_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_ext = Path(model_file.filename).suffix if model_file.filename else ""
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = models_dir / unique_filename
            
            # 保存文件并计算大小
            with open(file_path, "wb") as buffer:
                content = await model_file.read()
                buffer.write(content)
                calculated_file_size = len(content)  # 计算文件大小
            
            local_path = str(file_path)
        
        # 处理缩略图上传
        thumbnail_path = None
        if thumbnail_file:
            # 确保缩略图目录存在
            thumbnails_dir = Path("static/models/thumbnails")
            thumbnails_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_ext = Path(thumbnail_file.filename).suffix if thumbnail_file.filename else ""
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = thumbnails_dir / unique_filename
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                content = await thumbnail_file.read()
                buffer.write(content)
            
            thumbnail_path = str(file_path)
        
        # 确定最终的文件大小：优先使用计算出的大小，否则使用用户输入的大小
        final_file_size = calculated_file_size if calculated_file_size else file_size
        
        # 创建模型记录
        item = await ModelItem.create(
            name=name,
            description=description,
            category=category,
            orientation=orientation,
            local_path=local_path,
            url=url,
            thumbnail=thumbnail_path,
            file_size=final_file_size,
            is_show=is_show
        )
        # 记录操作日志
        await record_operation_log(
            request=request,
            username=current_user.username,
            operation_type="CREATE",
            operation_content=f"创建模型:{name}",
            target_type="model",
            target_id=item.id,
            user=current_user,
            details={"name": name, "description": description, "category": category, "orientation": orientation, "url": url, "file_size": final_file_size, "is_show": is_show},
        )
        # 转换为Pydantic模型并添加完整URL
        result = await Model_Pydantic.from_tortoise_orm(item)
        result_dict = result.dict()
        
        # 将本地路径转换为完整URL
        if result_dict.get('local_path'):
            result_dict['local_url'] = get_full_url(request, result_dict['local_path'])
        if result_dict.get('thumbnail'):
            result_dict['thumbnail_url'] = get_full_url(request, result_dict['thumbnail'])
            
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"创建模型失败: {str(e)}")

@router.get("/models", summary="获取模型列表")
async def list_models(request: Request, category: str = None, orientation: str = None):
    # 构建查询条件
    query = ModelItem.all()
    if category:
        query = query.filter(category=category)
    if orientation:
        query = query.filter(orientation=orientation)
    
    items = await Model_Pydantic.from_queryset(query.order_by("-created_at"))
    result = []
    
    for item in items:
        item_dict = item.dict()
        # 将本地路径转换为完整URL
        if item_dict.get('local_path'):
            item_dict['local_url'] = get_full_url(request, item_dict['local_path'])
        if item_dict.get('thumbnail'):
            item_dict['thumbnail_url'] = get_full_url(request, item_dict['thumbnail'])
        # 添加格式化的文件大小
        item_dict['file_size_formatted'] = format_file_size(item_dict.get('file_size'))
        result.append(item_dict)
    
    return result

@router.get("/models/{model_id}", summary="获取模型详情")
async def get_model(request: Request, model_id: int):
    item = await ModelItem.get_or_none(pk=model_id)
    if not item:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    result = await Model_Pydantic.from_tortoise_orm(item)
    result_dict = result.dict()
    
    # 将本地路径转换为完整URL
    if result_dict.get('local_path'):
        result_dict['local_url'] = get_full_url(request, result_dict['local_path'])
    if result_dict.get('thumbnail'):
        result_dict['thumbnail_url'] = get_full_url(request, result_dict['thumbnail'])
        
    return result_dict

@router.put("/models/{model_id}", summary="更新模型")
async def update_model(
    request: Request,
    model_id: int,
    name: str = Form(None),
    description: str = Form(None),
    category: str = Form(None),
    orientation: str = Form(None),
    url: str = Form(None),
    file_size: int = Form(None),
    is_show: bool = Form(None),
    model_file: UploadFile = File(None),
    thumbnail_file: UploadFile = File(None),
    current_user: User = Depends(get_current_user)
):
    item = await ModelItem.get_or_none(pk=model_id)
    if not item:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    try:
        update_data = {}
        
        # 处理基本字段更新
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if category is not None:
            update_data["category"] = category
        if orientation is not None:
            update_data["orientation"] = orientation
        if url is not None:
            update_data["url"] = url
        if file_size is not None:
            update_data["file_size"] = file_size
        if is_show is not None:
            update_data["is_show"] = is_show
        
        # 处理模型文件上传
        if model_file:
            # 验证文件格式
            if not model_file.filename.lower().endswith('.zip'):
                raise HTTPException(status_code=400, detail="模型文件必须是.zip格式")
                
            # 删除旧文件
            if item.local_path and os.path.exists(item.local_path):
                os.remove(item.local_path)
            
            # 确保模型目录存在
            models_dir = Path("static/models")
            models_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_ext = Path(model_file.filename).suffix if model_file.filename else ""
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = models_dir / unique_filename
            
            # 保存文件并计算大小
            with open(file_path, "wb") as buffer:
                content = await model_file.read()
                buffer.write(content)
                # 如果上传了新文件，自动更新文件大小
                update_data["file_size"] = len(content)
            
            update_data["local_path"] = str(file_path)
        
        # 处理缩略图上传
        if thumbnail_file:
            # 删除旧缩略图
            if item.thumbnail and os.path.exists(item.thumbnail):
                os.remove(item.thumbnail)
            
            # 确保缩略图目录存在
            thumbnails_dir = Path("static/models/thumbnails")
            thumbnails_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成唯一文件名
            file_ext = Path(thumbnail_file.filename).suffix if thumbnail_file.filename else ""
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = thumbnails_dir / unique_filename
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                content = await thumbnail_file.read()
                buffer.write(content)
            
            update_data["thumbnail"] = str(file_path)
        
        if update_data:
            await item.update_from_dict(update_data).save()
            # 记录操作日志
            await record_operation_log(
                request=request,
                username=current_user.username,
                operation_type="UPDATE",
                operation_content=f"更新模型:{item.name}",
                target_type="model",
                target_id=item.id,
                user=current_user,
            )
        
        # 转换为Pydantic模型并添加完整URL
        result = await Model_Pydantic.from_tortoise_orm(item)
        result_dict = result.dict()
        
        # 将本地路径转换为完整URL
        if result_dict.get('local_path'):
            result_dict['local_url'] = get_full_url(request, result_dict['local_path'])
        if result_dict.get('thumbnail'):
            result_dict['thumbnail_url'] = get_full_url(request, result_dict['thumbnail'])
            
        return result_dict
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"更新模型失败: {str(e)}")

@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除模型")
async def delete_model(model_id: int, request: Request, current_user: User = Depends(get_current_user)):
    item = await ModelItem.get_or_none(pk=model_id)
    if not item:
        # 记录操作日志
        await record_operation_log(
            request=request,
            username=current_user.username,
            operation_type="DELETE",
            operation_content=f"删除模型:{item.name}",
            target_type="model",
            target_id=item.id,
            user=current_user,
            status="failed",
            details={"name": item.name, "category": item.category, "orientation": item.orientation, "url": item.url, "file_size": item.file_size, "is_show": item.is_show},
        )
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 删除关联文件
    if item.local_path and os.path.exists(item.local_path):
        os.remove(item.local_path)
    if item.thumbnail and os.path.exists(item.thumbnail):
        os.remove(item.thumbnail)
    
    await item.delete()
    # 记录操作日志
    await record_operation_log(
        request=request,
        username=current_user.username,
        operation_type="DELETE",
        operation_content=f"删除模型:{item.name}",
        target_type="model",
        target_id=item.id,
        user=current_user,
        details={"name": item.name, "category": item.category, "orientation": item.orientation, "url": item.url, "file_size": item.file_size, "is_show": item.is_show},
    )
    return {"detail": "模型已删除"} 