from fastapi import HTTPException
from aiohttp import ClientError


class AudioExceptions(ClientError, HTTPException):
    def __init__(self, status_code:int, detail:str):
        self.status_code = status_code
        self.detail = detail

        ClientError.__init__(self, self.detail)
        HTTPException.__init__(self, self.status_code,  self.detail)

    def log_torture(self):
        """  用来记录失败的日志 """
        pass