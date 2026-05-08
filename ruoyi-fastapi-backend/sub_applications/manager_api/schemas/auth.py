from pydantic import BaseModel, Field


class XiaozhiLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    captchaId: str = ""
    captcha: str = ""
    mobileCaptcha: str = ""


class RuoyiLoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=255)
    code: str = ""
    uuid: str = ""


class ChangePasswordPayload(BaseModel):
    password: str = Field(min_length=1, max_length=255)
    newPassword: str = Field(min_length=1, max_length=255)
