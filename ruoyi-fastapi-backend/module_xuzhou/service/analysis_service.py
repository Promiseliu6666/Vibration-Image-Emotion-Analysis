import os
import traceback
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.entity.vo.analysis_vo import (
    BinhuaAnalysisModel,
    BinhuaAnalysisUpdateModel,
    DeleteBinhuaAnalysisModel,
    BinhuaAnalysisPageQueryModel,
)
from module_xuzhou.error.analysis_error import AnalysisNotFoundError
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class BinhuaAnalysisService:
    @classmethod
    async def get_analysis_list_services(
        cls,
        query_db: AsyncSession,
        query_object: BinhuaAnalysisPageQueryModel,
        is_page: bool = True,
    ):
        analysis_list_result = await BinhuaAnalysisDao.get_analysis_list(
            query_db, query_object, is_page
        )
        # 自动补充 videoUrl 和 videoPath（更健壮）
        if isinstance(analysis_list_result, dict) and "records" in analysis_list_result:
            for item in analysis_list_result["records"]:
                video_path = item.get("videoPath") or item.get("video_path") or item.get("videoPath")
                if video_path and item.get("id"):
                    item["videoUrl"] = f"/analysis/video/{item['id']}"
                    item["videoPath"] = str(video_path).strip()
        return analysis_list_result

    @classmethod
    async def get_analysis_history_services(
        cls, query_db: AsyncSession, person_id: int
    ) -> List[Dict[str, Any]]:
        result = []
        for analysis in await BinhuaAnalysisDao.get_analysis_list_by_person_id(
            query_db, person_id=person_id
        ):
            item = CamelCaseUtil.transform_result(analysis)
            video_path = item.get("videoPath") or item.get("video_path")
            if video_path and item.get("id"):
                item["videoUrl"] = f"/analysis/video/{item['id']}"
                item["videoPath"] = str(video_path).strip()
            result.append(item)
        return result

    @classmethod
    async def get_analysis_detail_services(
        cls, query_db: AsyncSession, analysis_id: int
    ) -> BinhuaAnalysisModel:
        analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        )
        if analysis:
            item = CamelCaseUtil.transform_result(analysis)
            video_path = item.get("videoPath") or item.get("video_path")
            if video_path and item.get("id"):
                item["videoUrl"] = f"/analysis/video/{item['id']}"
                item["videoPath"] = str(video_path).strip()
            return BinhuaAnalysisModel(**item)
        return BinhuaAnalysisModel()

    @classmethod
    async def add_analysis_services(
        cls, query_db: AsyncSession, analysis: BinhuaAnalysisModel
    ) -> int:
        try:
            analysis_id = await BinhuaAnalysisDao.add_analysis_dao(query_db, analysis)
            await query_db.commit()
            logger.info(f'新增分析记录成功，ID: {analysis_id}')
            return analysis_id
        except Exception as e:
            await query_db.rollback()
            logger.error(f'新增分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise

    @classmethod
    async def edit_analysis_services(
        cls,
        query_db: AsyncSession,
        analysis_update: BinhuaAnalysisUpdateModel,
        analysis_id: int,
    ):
        if not await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        ):
            raise AnalysisNotFoundError('分析记录不存在')

        try:
            update_dict = analysis_update.model_dump(exclude_unset=True)
            if not update_dict:
                return
            update_dict["id"] = analysis_id
            await BinhuaAnalysisDao.edit_analysis_dao(query_db, update_dict)
            await query_db.commit()
            logger.info(f'更新分析记录成功，ID: {analysis_id}')
        except Exception as e:
            await query_db.rollback()
            logger.error(f'更新分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise

    @classmethod
    async def delete_analysis_services(
        cls, query_db: AsyncSession, analysis_id: int
    ) -> bool:
        if await BinhuaAnalysisDao.get_analysis_detail_by_id(
            query_db, analysis_id=analysis_id
        ):
            try:
                await BinhuaAnalysisDao.delete_analysis_dao(query_db, analysis_id)
                await query_db.commit()
                logger.info(f'删除分析记录成功，ID: {analysis_id}')
                return True
            except Exception as e:
                await query_db.rollback()
                logger.error(f'删除分析记录失败: {e}')
                logger.error(traceback.format_exc())
                raise
        return False

    @classmethod
    async def export_person_report(
        cls, query_db: AsyncSession, analysis_id: int, radar_image: str
    ) -> bytes:
        """生成个人心理分析报告 PDF"""
        import base64
        import io
        import os
        from datetime import datetime

        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
        )
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # --- 查询分析记录 ---
        analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(query_db, analysis_id)
        if not analysis:
            raise AnalysisNotFoundError('分析记录不存在')

        # --- 注册中文字体 ---
        font_regular = None
        font_bold = None
        font_candidates = [
            ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"),
            ("C:/Windows/Fonts/simsun.ttc", "C:/Windows/Fonts/simhei.ttf"),
        ]
        for regular_path, bold_path in font_candidates:
            if os.path.exists(regular_path):
                font_regular = "ChineseFont"
                font_bold = "ChineseFontBold"
                pdfmetrics.registerFont(TTFont(font_regular, regular_path))
                if os.path.exists(bold_path):
                    pdfmetrics.registerFont(TTFont(font_bold, bold_path))
                else:
                    font_bold = font_regular
                break
        if not font_regular:
            font_regular = "Helvetica"
            font_bold = "Helvetica-Bold"

        # --- 调用 AI 生成评价 ---
        ai_text = await cls._generate_ai_evaluation(analysis)

        # --- 生成 PDF ---
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=20*mm, rightMargin=20*mm,
            topMargin=15*mm, bottomMargin=15*mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'ChTitle', fontName=font_bold, fontSize=22,
            alignment=TA_CENTER, spaceAfter=6*mm, leading=30,
        )
        subtitle_style = ParagraphStyle(
            'ChSubtitle', fontName=font_regular, fontSize=11,
            alignment=TA_CENTER, spaceAfter=10*mm, leading=16,
            textColor=HexColor('#666666'),
        )
        section_style = ParagraphStyle(
            'ChSection', fontName=font_bold, fontSize=14,
            spaceBefore=8*mm, spaceAfter=4*mm, leading=20,
        )
        body_style = ParagraphStyle(
            'ChBody', fontName=font_regular, fontSize=10,
            leading=18, spaceAfter=2*mm,
        )
        table_cell_style = ParagraphStyle(
            'ChCell', fontName=font_regular, fontSize=9, leading=14,
            alignment=TA_CENTER,
        )
        table_header_style = ParagraphStyle(
            'ChCellBold', fontName=font_bold, fontSize=9, leading=14,
            alignment=TA_CENTER,
        )

        story = []

        # 标题
        story.append(Paragraph("个人心理分析报告", title_style))
        person_label = getattr(analysis, 'person_name', None) or '未知'
        gen_time = datetime.now().strftime('%Y年%m月%d日 %H:%M')
        story.append(Paragraph(f"姓名：{person_label}　　　　生成时间：{gen_time}", subtitle_style))

        # --- 雷达图 ---
        story.append(Paragraph("雷达图分析", section_style))
        if radar_image:
            radar_data = radar_image
            if ',' in radar_data:
                radar_data = radar_data.split(',', 1)[1]
            try:
                img_bytes = base64.b64decode(radar_data)
                if not img_bytes:
                    raise ValueError("解码后的雷达图数据为空")
                img_buf = io.BytesIO(img_bytes)
                img = Image(img_buf, width=140*mm, height=105*mm)
                story.append(img)
            except Exception as e:
                logger.warning(f"雷达图解析失败: {e}, 数据长度={len(radar_image) if radar_image else 0}")
                story.append(Paragraph("[雷达图解析失败]", body_style))
        story.append(Spacer(1, 3*mm))

        # --- 指标数据表格 ---
        story.append(Paragraph("指标数据", section_style))
        e_labels = [
            ("e1", "攻击性"), ("e2", "压力"), ("e3", "焦虑"),
            ("e4", "可疑度"), ("e5", "情绪波动"), ("e6", "抑郁倾向"),
            ("e7", "社交意愿"), ("e8", "自信心"), ("e9", "适应能力"),
            ("e10", "冲动性"), ("e11", "自我认知"), ("e12", "同理心"),
            ("e13", "敌意"), ("e14", "稳定性"),
        ]
        table_data = [[
            Paragraph("指标", table_header_style),
            Paragraph("含义", table_header_style),
            Paragraph("数值", table_header_style),
        ]]
        for key, label in e_labels:
            val = getattr(analysis, key, 0) or 0
            table_data.append([
                Paragraph(key, table_cell_style),
                Paragraph(label, ParagraphStyle('ChCellL', fontName=font_regular, fontSize=9, leading=14, alignment=TA_LEFT)),
                Paragraph(f"{val:.2f}", table_cell_style),
            ])
        # 汇总行
        table_data.append([
            Paragraph("幸福指数", table_header_style),
            Paragraph("综合幸福指数", ParagraphStyle('ChCellL', fontName=font_regular, fontSize=9, leading=14, alignment=TA_LEFT)),
            Paragraph(f"{getattr(analysis, 'happiness_index', 0) or 0:.2f}", table_cell_style),
        ])
        happiness_level = getattr(analysis, 'happiness_level', None) or '-'
        safety_risk = getattr(analysis, 'safety_risk', None) or '-'
        table_data.append([
            Paragraph("幸福等级", table_header_style),
            Paragraph("", table_cell_style),
            Paragraph(happiness_level, table_cell_style),
        ])
        table_data.append([
            Paragraph("安全风险", table_header_style),
            Paragraph("", table_cell_style),
            Paragraph(safety_risk, table_cell_style),
        ])

        col_widths = [40*mm, 80*mm, 40*mm]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), HexColor('#F2F7FC')]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 3*mm))

        # --- AI 综合评估 ---
        story.append(Paragraph("AI 综合评估", section_style))
        ai_paragraphs = ai_text.split('\n')
        for p in ai_paragraphs:
            stripped = p.strip()
            if stripped:
                story.append(Paragraph(stripped, body_style))

        doc.build(story)
        pdf_bytes = buf.getvalue()
        buf.close()
        return pdf_bytes

    @classmethod
    async def _generate_ai_evaluation(cls, analysis) -> str:
        """调用 DashScope AI 生成心理评估建议"""
        from openai import AsyncOpenAI

        e_data = {f"e{i}": getattr(analysis, f"e{i}", 0) or 0 for i in range(1, 15)}
        happiness_index = getattr(analysis, 'happiness_index', 0) or 0
        happiness_level = getattr(analysis, 'happiness_level', None) or '未知'
        safety_risk = getattr(analysis, 'safety_risk', None) or '未知'

        prompt = f"""你是一位专业的心理学评估专家。请根据以下人员心理分析数据，撰写一份200-300字的综合评估报告，包含：
1. 整体心理状态概述
2. 关键指标分析（指出偏高或偏低的指标及其可能含义）
3. 针对性的改善建议

【分析数据】
- e1 攻击性: {e_data['e1']:.2f}
- e2 压力: {e_data['e2']:.2f}
- e3 焦虑: {e_data['e3']:.2f}
- e4 可疑度: {e_data['e4']:.2f}
- e5 情绪波动: {e_data['e5']:.2f}
- e6 抑郁倾向: {e_data['e6']:.2f}
- e7 社交意愿: {e_data['e7']:.2f}
- e8 自信心: {e_data['e8']:.2f}
- e9 适应能力: {e_data['e9']:.2f}
- e10 冲动性: {e_data['e10']:.2f}
- e11 自我认知: {e_data['e11']:.2f}
- e12 同理心: {e_data['e12']:.2f}
- e13 敌意: {e_data['e13']:.2f}
- e14 稳定性: {e_data['e14']:.2f}
- 幸福指数: {happiness_index:.2f}
- 幸福等级: {happiness_level}
- 安全风险: {safety_risk}

请直接输出评估报告正文，不要使用markdown标记。"""

        try:
            client = AsyncOpenAI(
                api_key=os.getenv("DASHSCOPE_API_KEY"),
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            response = await client.chat.completions.create(
                model="qwen3-omni-flash",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1024,
            )
            text = response.choices[0].message.content or ""
            return text.strip() or cls._fallback_evaluation(e_data, happiness_level, safety_risk)
        except Exception as e:
            logger.warning(f"AI evaluation failed: {e}, using fallback")
            return cls._fallback_evaluation(e_data, happiness_level, safety_risk)

    @classmethod
    def _fallback_evaluation(cls, e_data: dict, happiness_level: str, safety_risk: str) -> str:
        """基于规则生成兜底评估文本"""
        high_items = []
        low_items = []
        for i in range(1, 15):
            val = e_data.get(f'e{i}', 0)
            if val > 0.7:
                high_items.append(f"e{i}")
            elif val < 0.3:
                low_items.append(f"e{i}")

        parts = [f"综合评估：幸福等级为「{happiness_level}」，安全风险评估为「{safety_risk}」。"]
        if high_items:
            parts.append(f"偏高指标：{', '.join(high_items)}，建议重点关注。")
        if low_items:
            parts.append(f"偏低指标：{', '.join(low_items)}，可能需要改善。")
        if not high_items and not low_items:
            parts.append("各项指标处于正常范围，心理状态总体稳定。")
        parts.append("（注：本评估基于数据规则自动生成，仅供参考，详细评估请等待 AI 分析恢复。）")
        return ' '.join(parts)

    @classmethod
    async def batch_delete_analysis_services(
        cls, query_db: AsyncSession, delete_model: DeleteBinhuaAnalysisModel
    ):
        analysis_ids_str = delete_model.analysis_ids.strip()
        if not analysis_ids_str:
            return

        analysis_ids = [int(aid) for aid in analysis_ids_str.split(",") if aid.strip().isdigit()]
        if not analysis_ids:
            return

        try:
            await BinhuaAnalysisDao.batch_delete_analysis_dao(query_db, analysis_ids)
            await query_db.commit()
            logger.info(f'批量删除分析记录成功，IDs: {analysis_ids}')
        except Exception as e:
            await query_db.rollback()
            logger.error(f'批量删除分析记录失败: {e}')
            logger.error(traceback.format_exc())
            raise