FROM python:3.11

# 修改pip源配置
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ && \
    pip config set install.trusted-host mirrors.aliyun.com

# 复制本地ffmpeg二进制文件
COPY ffmpeg/bin/ffmpeg /usr/local/bin/
COPY ffmpeg/bin/ffprobe /usr/local/bin/
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖，使用阿里云源
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建音频缓存目录
ARG CACHE_DIR=audio_cache
RUN mkdir -p ${CACHE_DIR}

# 安装生产级别的 ASGI 服务器
RUN pip install --no-cache-dir gunicorn uvicorn[standard]

# 使用 gunicorn 启动 原命令
# CMD ["sh", "-c", "gunicorn app:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:${FASTAPI_PORT} --timeout 300"]

CMD ["sh", "-c", \
"gunicorn app.factory:create_app \
--workers ${GUNICORN_WORKERS:-4} \
--worker-class uvicorn.workers.UvicornWorker \
--bind 0.0.0.0:${FASTAPI_PORT} \
--timeout 300"]
