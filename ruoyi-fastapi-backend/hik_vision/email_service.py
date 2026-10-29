# hik_vision/email_service.py
import os
import traceback
from datetime import datetime
from typing import Optional

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

# ====================== 邮箱配置 ======================
conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", 465)),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "振动分析系统"),
    MAIL_STARTTLS=os.getenv("MAIL_STARTTLS", "False").lower() == "true",
    MAIL_SSL_TLS=os.getenv("MAIL_SSL_TLS", "True").lower() == "true",
    USE_CREDENTIALS=os.getenv("MAIL_USE_CREDENTIALS", "True").lower() == "true",
    VALIDATE_CERTS=os.getenv("MAIL_VALIDATE_CERTS", "True").lower() == "true",
)

fm = FastMail(conf)


async def send_analysis_email(
        source: str,
        state: dict,
        results: dict,
        video_path: Optional[str] = None,
        recipient: Optional[str] = None
) -> bool:
    """仅在幸福指数 < 60 且识别到具体人员时发送邮件"""
    if os.getenv("MAIL_ENABLED", "true").lower() != "true":
        return False
    try:
        recipient_email = recipient or os.getenv("RECIPIENT_EMAIL")
        if not recipient_email:
            print(f"[{source}] 未配置收件人邮箱，跳过发送")
            return False

        # 支持从快照或原始state中获取信息
        person_name = state.get("person_name") or state.get("matched_person") or "Unknown"
        person_id = state.get("person_id") or "未知ID"

        if person_name == "Unknown" or not person_id:
            print(f"[{source}] 未识别到具体人员，跳过邮件发送")
            return False

        happiness_index = float(results.get("e12", 0.0))

        if happiness_index >= 60:
            print(f"[{source}] 幸福指数 {happiness_index:.1f} ≥ 60，不属于低幸福等级，跳过邮件发送")
            return False

        happiness_level = "低"
        safety_risk = "高风险" if happiness_index < 40 else "中风险"

        subject = f"【预警】低幸福指数 - {person_name} {source.upper()} 分析完成"

        body = f"""【振动分析低幸福指数预警报告】

人员姓名：{person_name}
人员ID：{person_id}
幸福指数：{happiness_index:.1f}（{happiness_level}）
安全风险等级：{safety_risk}
分析来源：{source}
分析完成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
视频文件：{video_path or '无'}

振动参数详情：
- E1 (头部晃动): {results.get("e1", 0.0):.2f}
- E2 (面部微表情): {results.get("e2", 0.0):.2f}
- E3 (眼部活动): {results.get("e3", 0.0):.2f}
- E4 (嘴部活动): {results.get("e4", 0.0):.2f}
- E5 (颈部紧张度): {results.get("e5", 0.0):.2f}
- E6 (整体稳定性): {results.get("e6", 0.0):.2f}
- E7 (呼吸频率): {results.get("e7", 0.0):.2f}
- E8 (心率变异性): {results.get("e8", 0.0):.2f}
- E9 (面部对称性): {results.get("e9", 0.0):.2f}
- E10 (面部肌肉紧张度): {results.get("e10", 0.0):.2f}
- E11 (情绪波动): {results.get("e11", 0.0):.2f}
- E12 (幸福指数): {results.get("e12", 0.0):.2f}
- E13 (压力指数): {results.get("e13", 0.0):.2f}
- E14 (疲劳指数): {results.get("e14", 0.0):.2f}

⚠️ 注意：该人员本次幸福指数处于较低水平，请关注其心理状态或工作压力情况。

详细振动参数已保存至系统后台。
视频文件保存在服务器，可通过系统查看。

振动分析系统
"""

        message = MessageSchema(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            subtype=MessageType.plain,
        )

        await fm.send_message(message)
        print(f"[{source}] ✅ 低幸福指数预警邮件已发送 → {recipient_email} | 幸福指数: {happiness_index:.1f}")
        return True

    except Exception as e:
        print(f"[{source}] ❌ 邮件发送失败: {e}")
        traceback.print_exc()
        return False