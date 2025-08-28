from pydantic import BaseModel


class ClearCacheFilesSchema(BaseModel):
    password: str
    order: str