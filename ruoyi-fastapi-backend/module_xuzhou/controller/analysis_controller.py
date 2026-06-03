import os
import traceback
from pathlib import Path

import httpx
from fastapi import Header, status, APIRouter, Depends, Request, Body, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.enums import BusinessType
from config.get_db import get_db
from module_admin.annotation.integration_log_annotation import integration_log
from module_xuzhou.auth import unified_auth
from module_xuzhou.entity.vo.analysis_vo import (
    BinhuaAnalysisModel,
    BinhuaAnalysisUpdateModel,
    DeleteBinhuaAnalysisModel,
    BinhuaAnalysisPageQueryModel,
    ExportPersonReportModel,
)
from module_xuzhou.service.analysis_service import BinhuaAnalysisService
from module_xuzhou.dao.analysis_dao import BinhuaAnalysisDao
from module_xuzhou.error.analysis_error import AnalysisNotFoundError
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.response_util import ResponseUtil
from fastapi import HTTPException

analysis_controller = APIRouter(prefix='/analysis', dependencies=[Depends(unified_auth)])


@analysis_controller.get('/list', response_model=PageResponseModel, summary='获取分析记录列表')
@integration_log(
    title='获取分析记录列表',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_list(
        request: Request,
        query: BinhuaAnalysisPageQueryModel = Depends(BinhuaAnalysisPageQueryModel.as_query),
        query_db: AsyncSession = Depends(get_db),
):
    result = await BinhuaAnalysisService.get_analysis_list_services(
        query_db, query, is_page=True
    )
    return ResponseUtil.success(data=result)


@analysis_controller.get('/person/{person_id}', summary='获取指定人员的所有分析历史记录')
@integration_log(
    title='获取人员分析历史',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_history(
        request: Request,
        person_id: int,
        query_db: AsyncSession = Depends(get_db),
):
    result = await BinhuaAnalysisService.get_analysis_history_services(query_db, person_id)
    return ResponseUtil.success(data=result)


@analysis_controller.get('/{analysis_id}', response_model=BinhuaAnalysisModel, summary='获取分析记录详细信息')
@integration_log(
    title='获取分析记录详细信息',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_detail(
        request: Request,
        analysis_id: int,
        query_db: AsyncSession = Depends(get_db),
):
    result = await BinhuaAnalysisService.get_analysis_detail_services(query_db, analysis_id)
    return ResponseUtil.success(data=result)


@analysis_controller.post('/', summary='新增分析记录')
@integration_log(
    title='新增分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.INSERT,
)
async def add_analysis(
        request: Request,
        analysis: BinhuaAnalysisModel,
        query_db: AsyncSession = Depends(get_db),
):
    try:
        new_id = await BinhuaAnalysisService.add_analysis_services(query_db, analysis)
        return ResponseUtil.success(data={"new_analysis_id": new_id}, msg='新增成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'新增分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'新增失败: {str(e)}')


@analysis_controller.put('/{analysis_id}', summary='编辑分析记录')
@integration_log(
    title='编辑分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.UPDATE,
)
async def edit_analysis(
        request: Request,
        analysis_id: int,
        analysis_update: BinhuaAnalysisUpdateModel,
        query_db: AsyncSession = Depends(get_db),
):
    try:
        await BinhuaAnalysisService.edit_analysis_services(query_db, analysis_update, analysis_id)
        return ResponseUtil.success(msg='修改成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'编辑分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'修改失败: {str(e)}')


@analysis_controller.delete('/{analysis_id}', summary='删除分析记录')
@integration_log(
    title='删除分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def delete_analysis(
        request: Request,
        analysis_id: int,
        query_db: AsyncSession = Depends(get_db),
):
    try:
        result = await BinhuaAnalysisService.delete_analysis_services(query_db, analysis_id)
        if result:
            return ResponseUtil.success(msg='删除成功')
        else:
            return ResponseUtil.error(msg='分析记录不存在')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'删除分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'删除失败: {str(e)}')


@analysis_controller.post('/export-person-report', summary='导出个人心理分析报告 PDF')
@integration_log(
    title='导出个人心理分析报告 PDF',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def export_person_report(
        request: Request,
        export_model: ExportPersonReportModel = Body(...),
        query_db: AsyncSession = Depends(get_db),
):
    try:
        pdf_bytes = await BinhuaAnalysisService.export_person_report(
            query_db,
            export_model.analysis_id,
            export_model.radar_image,
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=psychological_report.pdf",
            },
        )
    except AnalysisNotFoundError:
        raise HTTPException(status_code=404, detail='分析记录不存在')
    except Exception as e:
        logger.error(f'导出个人报告失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'导出报告失败: {str(e)}')


@analysis_controller.post('/batch-delete', summary='批量删除分析记录')
@integration_log(
    title='批量删除分析记录',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def batch_delete_analysis(
        request: Request,
        delete_model: DeleteBinhuaAnalysisModel,
        query_db: AsyncSession = Depends(get_db),
):
    try:
        await BinhuaAnalysisService.batch_delete_analysis_services(query_db, delete_model)
        return ResponseUtil.success(msg='批量删除成功')
    except Exception as e:
        await query_db.rollback()
        logger.error(f'批量删除分析记录失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'批量删除失败: {str(e)}')

def parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int]:
    if not range_header or not range_header.startswith("bytes="):
        return 0, file_size - 1
    try:
        h = range_header.replace("bytes=", "").split("-")
        start = int(h[0]) if h[0] else 0
        end = int(h[1]) if h[1] else file_size - 1
        if start > end or start < 0 or end >= file_size:
            raise ValueError
        return start, end
    except:
        return 0, file_size - 1


def send_bytes_range_requests(file_obj, start: int, end: int, chunk_size: int = 64 * 1024):
    with file_obj as f:
        f.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            yield data
            remaining -= len(data)
@analysis_controller.get('/video/{analysis_id}', summary='获取分析视频文件（支持盒子代理）')
@integration_log(
    title='获取分析视频文件',
    system_name='徐州人员管理系统',
    business_type=BusinessType.OTHER,
)
async def get_analysis_video(
        request: Request,
        analysis_id: int,
        range: str = Header(None),
        query_db: AsyncSession = Depends(get_db)
):
    try:
        analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(query_db, analysis_id)
        if not analysis or not analysis.video_path:
            raise HTTPException(status_code=404, detail="视频文件不存在")

        video_path = str(analysis.video_path).strip()
        box_serial = getattr(analysis, 'box_serial', None)

        # 盒子视频：代理到盒子本地 API
        if box_serial:
            from module_xuzhou.controller.command_controller import box_registry
            from module_xuzhou.service.box_network import build_box_base_urls

            box = box_registry.get(str(box_serial))
            if not box:
                raise HTTPException(status_code=503, detail=f"盒子 {box_serial} 不在线")

            base_urls = build_box_base_urls(box)
            if not base_urls:
                raise HTTPException(status_code=503, detail=f"盒子 {box_serial} IP 未知")

            filename = os.path.basename(video_path) or Path(video_path).name
            box_video_url = f"{base_urls[0]}/videos/{filename}"

            req_headers = {"Cache-Control": "no-cache"}
            if range:
                req_headers["Range"] = range

            logger.info(f"代理盒子视频 - ID:{analysis_id} | box:{box_serial} | url:{box_video_url}")

            async def _proxy_box_video():
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream("GET", box_video_url, headers=req_headers) as resp:
                        if resp.status_code >= 400:
                            raise HTTPException(status_code=resp.status_code, detail="盒子视频获取失败")
                        async for chunk in resp.aiter_bytes(65536):
                            yield chunk

            proxy_headers = {
                "Content-Type": "video/mp4",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache",
            }
            return StreamingResponse(
                _proxy_box_video(),
                media_type="video/mp4",
                headers=proxy_headers,
                status_code=206 if range else 200,
            )

        # 服务器本地视频
        file_path = os.path.abspath(video_path)
        if not os.path.exists(file_path):
            logger.error(f"视频文件不存在: {file_path} (ID: {analysis_id})")
            raise HTTPException(status_code=404, detail="视频文件不存在")

        file_size = os.path.getsize(file_path)
        media_type = "video/mp4"

        logger.info(f"视频请求 - ID:{analysis_id} | 文件:{file_path} | 大小:{file_size} bytes | Range:{range}")

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": media_type,
            "Cache-Control": "no-cache",
            "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        }

        if range is None:
            headers["Content-Length"] = str(file_size)
            return StreamingResponse(
                open(file_path, "rb"),
                media_type=media_type,
                headers=headers,
                status_code=200
            )

        start, end = parse_range_header(range, file_size)
        chunk_size = end - start + 1
        headers["Content-Length"] = str(chunk_size)
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

        return StreamingResponse(
            send_bytes_range_requests(open(file_path, "rb"), start, end),
            media_type=media_type,
            headers=headers,
            status_code=206
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'获取视频失败 (ID={analysis_id}): {str(e)}')
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="视频服务异常，请检查后端日志")

# ==================== 批量删除时同时删除视频文件 ====================
@analysis_controller.post('/batch-delete-with-video', summary='批量删除分析记录及对应视频')
@integration_log(
    title='批量删除分析记录及视频',
    system_name='徐州人员管理系统',
    business_type=BusinessType.DELETE,
)
async def batch_delete_analysis_with_video(
        request: Request,
        delete_model: DeleteBinhuaAnalysisModel,
        query_db: AsyncSession = Depends(get_db),
):
    try:
        analysis_ids_str = delete_model.analysis_ids.strip()
        if not analysis_ids_str:
            return ResponseUtil.success(msg='没有需要删除的记录')

        analysis_ids = [int(aid) for aid in analysis_ids_str.split(",") if aid.strip().isdigit()]
        if not analysis_ids:
            return ResponseUtil.success(msg='没有有效的ID')

        deleted_count = 0
        deleted_videos = 0

        for aid in analysis_ids:
            analysis = await BinhuaAnalysisDao.get_analysis_detail_by_id(query_db, aid)
            if analysis:
                if analysis.video_path and os.path.exists(analysis.video_path):
                    try:
                        os.remove(analysis.video_path)
                        deleted_videos += 1
                        logger.info(f"已删除视频文件: {analysis.video_path}")
                    except Exception as ve:
                        logger.warning(f"删除视频文件失败: {analysis.video_path} - {ve}")

                await BinhuaAnalysisDao.delete_analysis_dao(query_db, aid)
                deleted_count += 1

        await query_db.commit()

        logger.info(f'批量删除 {deleted_count} 条记录及 {deleted_videos} 个视频文件成功')
        return ResponseUtil.success(
            msg=f'成功删除 {deleted_count} 条记录及 {deleted_videos} 个视频文件'
        )

    except Exception as e:
        await query_db.rollback()
        logger.error(f'批量删除分析记录及视频失败: {str(e)}')
        logger.error(traceback.format_exc())
        return ResponseUtil.error(msg=f'批量删除失败: {str(e)}')