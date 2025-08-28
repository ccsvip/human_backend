import asyncio
import psutil
import time
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException
from core.logger import logger
from core.redis_client import redis_client
from .models import Device, App, MediaFile
from typing import Dict, List, Any
import os

# 创建路由器
router = APIRouter()

@router.get("/dashboard", description="获取仪表盘概览数据", summary="仪表盘概览")
async def get_dashboard_data(request: Request):
    """获取仪表盘概览数据"""
    try:
        # 从AudioData表获取今日对话数
        from api_versions.v2.models import AudioData
        from settings.config import GREETING_LIST
        
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # 获取今日的所有音频数据，排除问候语
        today_audio_data = await AudioData.filter(
            created_at__gte=today_start,
            created_at__lte=today_end
        ).exclude(user_question__in=GREETING_LIST).values('user_question')
        
        # 按问题分组统计（去重），就像AudioData.vue中的逻辑一样
        unique_questions = set()
        for item in today_audio_data:
            unique_questions.add(item['user_question'])
        
        today_chats = len(unique_questions)
        
        # 获取设备数量
        device_count = await Device.all().count()
        
        # 获取全部应用数量
        app_count = await App.all().count()
        
        # 从AudioData表获取平均TTS响应时间
        # 获取最近100条有TTS耗时数据的记录
        recent_audio_data = await AudioData.filter(
            tts_started_at__isnull=False,
            tts_completed_at__isnull=False
        ).exclude(user_question__in=GREETING_LIST).order_by('-created_at').limit(100)
        
        if recent_audio_data:
            total_duration = 0
            count = 0
            for audio_data in recent_audio_data:
                if audio_data.tts_started_at and audio_data.tts_completed_at:
                    # 计算TTS耗时（毫秒）
                    duration_seconds = (audio_data.tts_completed_at - audio_data.tts_started_at).total_seconds()
                    total_duration += duration_seconds * 1000  # 转换为毫秒
                    count += 1
            
            avg_response_time = total_duration / count if count > 0 else 0
        else:
            avg_response_time = 0
        
        # 获取系统状态
        system_status = await get_system_status()
        
        # 获取系统资源使用情况
        system_resources = await get_system_resources()
        
        return {
            "todayChats": today_chats,
            "deviceCount": device_count,
            "appCount": app_count,
            "avgResponseTime": int(avg_response_time),
            "systemStatus": system_status,
            "systemResources": system_resources
        }
        
    except Exception as e:
        logger.error(f"获取仪表盘数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取仪表盘数据失败: {str(e)}")

@router.get("/chat-trends", description="获取对话趋势数据", summary="对话趋势")
async def get_chat_trends(request: Request, period: str = "24h"):
    """获取对话趋势数据"""
    try:
        from api_versions.v2.models import AudioData
        from settings.config import GREETING_LIST
        
        if period == "24h":
            # 获取24小时数据
            data = []
            now = datetime.now()
            for i in range(24):
                hour_time = now - timedelta(hours=23-i)
                # 如果数据库存储的是UTC时间，需要将查询时间转换为UTC
                hour_start_utc = hour_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=8)
                hour_end_utc = hour_start_utc + timedelta(hours=1)
                
                # 从AudioData表获取该小时的对话数（按问题分组）
                hour_audio_data = await AudioData.filter(
                    created_at__gte=hour_start_utc,
                    created_at__lt=hour_end_utc
                ).exclude(user_question__in=GREETING_LIST)
                
                # 按问题去重统计
                unique_questions = set()
                for audio_data in hour_audio_data:
                    unique_questions.add(audio_data.user_question)
                count = len(unique_questions)
                
                data.append({
                    "time": hour_time.strftime("%H:00"),
                    "count": count
                })
        else:  # 7d
            # 获取7天数据
            data = []
            now = datetime.now()
            for i in range(7):
                day_time = now - timedelta(days=6-i)
                day_start = datetime.combine(day_time.date(), datetime.min.time())
                day_end = datetime.combine(day_time.date(), datetime.max.time())
                
                # 从AudioData表获取该天的对话数（按问题分组）
                day_audio_data = await AudioData.filter(
                    created_at__gte=day_start,
                    created_at__lte=day_end
                ).exclude(user_question__in=GREETING_LIST).values('user_question')
                
                # 按问题去重统计
                unique_questions = set()
                for item in day_audio_data:
                    unique_questions.add(item['user_question'])
                count = len(unique_questions)
                
                data.append({
                    "time": day_time.strftime("%m/%d"),
                    "count": count
                })
        
        return {
            "period": period,
            "data": data
        }
        
    except Exception as e:
        logger.error(f"获取对话趋势数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取对话趋势数据失败: {str(e)}")

@router.get("/user-activity", description="获取用户活跃度分布", summary="用户活跃度")
async def get_user_activity(request: Request):
    """获取用户活跃度分布"""
    try:
        from api_versions.v2.models import AudioData
        from settings.config import GREETING_LIST
        
        # 获取最近7天的数据进行统计
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        # 获取所有音频数据，排除问候语
        audio_data_list = await AudioData.filter(
            created_at__gte=seven_days_ago
        ).exclude(user_question__in=GREETING_LIST)
        
        # 统计不同时段的活跃度（按问题分组去重）
        morning_questions = set()    # 9-12点
        afternoon_questions = set()  # 14-18点
        evening_questions = set()    # 19-23点
        other_questions = set()      # 其他时间
        
        for audio_data in audio_data_list:
            created_at = audio_data.created_at
            question = audio_data.user_question
            
            # 如果数据库存储的是UTC时间，需要转换为本地时间
            # UTC时间 + 8小时 = 本地时间
            local_time = created_at + timedelta(hours=8)
            hour = local_time.hour
            
            if 9 <= hour <= 12:
                morning_questions.add(question)
            elif 14 <= hour <= 18:
                afternoon_questions.add(question)
            elif 19 <= hour <= 23:
                evening_questions.add(question)
            else:
                other_questions.add(question)
        
        morning_count = len(morning_questions)
        afternoon_count = len(afternoon_questions)
        evening_count = len(evening_questions)
        other_count = len(other_questions)
        
        return {
            "data": [
                {"name": "上午(9-12点)", "value": morning_count},
                {"name": "下午(14-18点)", "value": afternoon_count},
                {"name": "晚上(19-23点)", "value": evening_count},
                {"name": "其他时间", "value": other_count}
            ]
        }
        
    except Exception as e:
        logger.error(f"获取用户活跃度数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取用户活跃度数据失败: {str(e)}")

@router.get("/topics", description="获取热门话题统计", summary="热门话题")
async def get_topics(request: Request):
    """获取热门话题统计"""
    try:
        from api_versions.v2.models import AudioData
        from settings.config import GREETING_LIST
        from tortoise.queryset import Q
        
        # 从AudioData表获取所有用户问题，排除问候语
        audio_data_list = await AudioData.filter().exclude(
            user_question__in=GREETING_LIST
        ).values('user_question')
        
        # 获取所有不同的问题
        unique_questions = set()
        for item in audio_data_list:
            question = item['user_question']
            unique_questions.add(question)
        
        # 将问题转换为列表并排序（按字母顺序或长度）
        questions_list = list(unique_questions)
        questions_list.sort()  # 按字母顺序排序
        
        # 取前5个问题，每个问题显示为被问了1次
        topics_data = []
        for i, question in enumerate(questions_list[:5]):
            topics_data.append({
                "name": question[:20] + "..." if len(question) > 20 else question,  # 限制显示长度
                "value": 1  # 每个不同的问题算作1次
            })
        
        # 如果数据不足5个，用默认数据补充
        if len(topics_data) < 5:
            default_topics = [
                "技术问题", "产品咨询", "使用帮助", "功能建议", "故障报告"
            ]
            for i in range(len(topics_data), 5):
                if i < len(default_topics):
                    topics_data.append({
                        "name": default_topics[i],
                        "value": 0
                    })
        
        return {"data": topics_data}
        
    except Exception as e:
        logger.error(f"获取热门话题数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取热门话题数据失败: {str(e)}")

async def get_system_status() -> Dict[str, bool]:
    """获取系统状态"""
    try:
        # 检查Redis连接
        redis_status = True
        try:
            await redis_client.ping()
        except:
            redis_status = False
        
        # 检查数据库连接（这里假设使用Tortoise ORM）
        database_status = True
        try:
            # 简单的数据库查询测试
            await Device.all().limit(1)
        except:
            database_status = False
        
        # 检查LLM服务状态（可以通过检查相关进程或服务来判断）
        llm_status = True  # 这里可以根据实际情况检查LLM服务
        
        return {
            "redis": redis_status,
            "database": database_status,
            "llm": llm_status
        }
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        return {
            "redis": False,
            "database": False,
            "llm": False
        }

async def get_system_resources() -> Dict[str, int]:
    """获取系统资源使用情况"""
    try:
        # 获取CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # 获取内存使用率
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # 获取磁盘使用率（Windows系统使用C盘）
        try:
            disk = psutil.disk_usage('C:' if os.name == 'nt' else '/')
            disk_percent = (disk.used / disk.total) * 100
        except:
            disk_percent = 0
        
        # 获取GPU使用率
        gpu_percent = 0
        try:
            import GPUtil
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu_percent = int(gpus[0].load * 100)
        except:
            # 如果没有GPU或获取失败，设为0
            gpu_percent = 0
        
        return {
            "cpu": int(cpu_percent),
            "memory": int(memory_percent),
            "disk": int(disk_percent),
            "gpu": gpu_percent
        }
        
    except Exception as e:
        logger.error(f"获取系统资源数据失败: {e}")
        return {
            "cpu": 0,
            "memory": 0,
            "disk": 0,
            "gpu": 0
        }

# 辅助函数：记录对话统计
async def record_chat_stats():
    """记录对话统计数据"""
    try:
        now = datetime.now()
        
        # 记录今日对话数
        today_key = f"stats:chats:{now.strftime('%Y-%m-%d')}"
        await redis_client.incr(today_key)
        await redis_client.expire(today_key, 86400 * 7)  # 保存7天
        
        # 记录小时对话数
        hour_key = f"stats:chats:hour:{now.strftime('%Y-%m-%d:%H')}"
        await redis_client.incr(hour_key)
        await redis_client.expire(hour_key, 86400 * 2)  # 保存2天
        
        # 记录用户活跃度
        hour = now.hour
        if 9 <= hour <= 12:
            await redis_client.incr("stats:activity:morning")
        elif 14 <= hour <= 18:
            await redis_client.incr("stats:activity:afternoon")
        elif 19 <= hour <= 23:
            await redis_client.incr("stats:activity:evening")
        else:
            await redis_client.incr("stats:activity:other")
            
    except Exception as e:
        logger.error(f"记录对话统计失败: {e}")

# 辅助函数：记录响应时间
async def record_response_time(response_time: float):
    """记录响应时间"""
    try:
        response_times_key = "stats:response_times"
        await redis_client.lpush(response_times_key, str(response_time))
        await redis_client.ltrim(response_times_key, 0, 99)  # 只保留最近100次
    except Exception as e:
        logger.error(f"记录响应时间失败: {e}")

# 辅助函数：记录在线用户
async def record_online_user(user_id: str):
    """记录在线用户"""
    try:
        online_users_key = "stats:online_users"
        await redis_client.sadd(online_users_key, user_id)
        await redis_client.expire(online_users_key, 300)  # 5分钟过期
    except Exception as e:
        logger.error(f"记录在线用户失败: {e}")

# 辅助函数：记录话题统计
async def record_topic_stats(topic_type: str):
    """记录话题统计"""
    try:
        topic_key = f"stats:topics:{topic_type}"
        await redis_client.incr(topic_key)
    except Exception as e:
        logger.error(f"记录话题统计失败: {e}")