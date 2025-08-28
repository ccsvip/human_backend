import hashlib
import time
import uuid

def add_auth_params(app_key, app_secret, params):
    q = params.get('q')
    if q is None:
        q = params.get('img')
    salt = str(uuid.uuid1())
    curtime = str(int(time.time()))  # 关键修复：参数名必须是 curtime
    sign = calculate_sign(app_key, app_secret, q, salt, curtime)
    params['appKey'] = app_key
    params['salt'] = salt
    params['curtime'] = curtime  # 官方要求字段名是 curtime
    params['signType'] = 'v3'
    params['sign'] = sign

def calculate_sign(app_key, app_secret, q, salt, curtime):
    src = app_key + get_input(q) + salt + curtime + app_secret
    return encrypt(src)

def encrypt(src):
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(src.encode('utf-8'))
    return hash_algorithm.hexdigest()

def get_input(content):
    if content is None:
        return content  # 修复：使用参数名 content 而非内置函数 input
    input_len = len(content)
    return content if input_len <= 20 else content[:10] + str(input_len) + content[-10:]
