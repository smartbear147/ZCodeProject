"""FastAPI 应用入口。"""

import logging

# ⚠️ 阿里云 nls SDK 把所有内部错误都走 logging.debug 输出,且不会回调用户传的
# on_error。必须把根 logger 调到 DEBUG,否则 NLS 建连/识别的错误会被完全吞掉,
# 表现为"start 返回 ok 但什么都没发生"。这里在导入 FastAPI 之前先配置好。
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audio, chat

app = FastAPI(title="Interview Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(audio.router)
app.include_router(chat.router)
