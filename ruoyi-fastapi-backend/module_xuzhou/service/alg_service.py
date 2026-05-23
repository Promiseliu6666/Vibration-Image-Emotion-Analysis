import json
import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from module_admin.dao.log_dao import IntegrationLogDao
from module_xuzhou.dao.alg_dao import AlgDao
from module_xuzhou.dao.scene_dao import SceneDao
from module_xuzhou.dao.video_dao import VideoDao
from module_xuzhou.entity.vo.alg_vo import AlgModel, AlgPageQueryModel
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class AlgService:
    """
    算法管理模块服务层
    """

    WEIGHT_ROOT = Path('algorithm') / 'model'
    ALLOWED_WEIGHT_EXTENSIONS = {'.onnx', '.pt', '.pth', '.bin', '.engine'}

    @staticmethod
    def safe_path_part(value: str) -> str:
        if not value:
            raise ValueError('路径片段不能为空')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
            raise ValueError('路径片段只能包含字母、数字、下划线、短横线和点')
        return value

    @classmethod
    def validate_weight_extension(cls, filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in cls.ALLOWED_WEIGHT_EXTENSIONS:
            raise ValueError('不支持的权重文件类型')
        return suffix

    @classmethod
    def build_weight_relative_path(cls, alg_serial: str, alg_version: str, filename: str) -> str:
        safe_serial = cls.safe_path_part(alg_serial)
        safe_version = cls.safe_path_part(alg_version)
        safe_name = cls.safe_path_part(Path(filename).name)
        cls.validate_weight_extension(safe_name)
        return str(cls.WEIGHT_ROOT / safe_serial / safe_version / safe_name).replace('\\', '/')

    @classmethod
    async def upload_weight_services(
        cls,
        query_db: AsyncSession,
        alg_name: str,
        alg_serial: str,
        alg_runtime_type: str,
        alg_default_conf: str | None,
        upload_file,
    ):
        existing = await AlgDao.get_alg_by_serial_version(query_db, alg_serial, alg_version)
        if existing:
            raise ValueError('该算法版本已存在')

        relative_path = cls.build_weight_relative_path(alg_serial, alg_version, upload_file.filename)
        full_path = Path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with full_path.open('wb') as weight_file:
            while chunk := await upload_file.read(1024 * 1024):
                weight_file.write(chunk)

        alg = AlgModel(
            alg_name=alg_name,
            alg_serial=alg_serial,
            alg_version=alg_version,
            alg_default_conf=alg_default_conf or '{}',
            alg_weight_path=relative_path,
            alg_runtime_type=alg_runtime_type,
            alg_enabled=True,
            alg_update_time=datetime.now(),
        )
        db_alg = await AlgDao.add_alg_dao(query_db, alg)
        await query_db.commit()
        return db_alg

    @staticmethod
    def algorithm_is_bound(video_rows: list, alg_id: int) -> bool:
        for row in video_rows:
            raw_algorithms = row.get('vidAlgorithm') or row.get('vid_algorithm') or []
            if isinstance(raw_algorithms, str):
                try:
                    raw_algorithms = json.loads(raw_algorithms)
                except json.JSONDecodeError:
                    raw_algorithms = []
            if not isinstance(raw_algorithms, list):
                continue
            for item in raw_algorithms:
                if isinstance(item, dict) and int(item.get('algId') or item.get('alg_id') or 0) == int(alg_id):
                    return True
        return False

    @classmethod
    async def get_alg_list_services(
        cls, query_db: AsyncSession, query_object: AlgPageQueryModel, is_page: bool = False
    ):
        """
        获取算法列表信息service

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 算法列表信息对象
        """
        alg_list_result = await AlgDao.get_alg_list(query_db, query_object, is_page)
        if hasattr(alg_list_result, 'rows') and isinstance(alg_list_result.rows, list):
            for item in alg_list_result.rows:
                if 'algDefaultConf' in item:
                    item['algDefaultConf'] = json.loads(item['algDefaultConf'])

        return alg_list_result

    @classmethod
    async def alg_detail_services(cls, query_db: AsyncSession, alg_id: int):
        """
        获取算法详细信息service

        :param query_db: orm对象
        :param alg_id: 算法id
        :return: 算法id对应的信息
        """
        alg = await AlgDao.get_alg_detail_by_id(query_db, alg_id=alg_id)
        if alg:
            result = AlgModel(**CamelCaseUtil.transform_result(alg))
        else:
            result = AlgModel(**dict())

        return result

    @classmethod
    async def alg_details_services(cls, query_db: AsyncSession, alg_ids: list):
        """
        批量获取算法详细信息service

        :param query_db: orm对象
        :param alg_ids: 算法id列表
        :return: 算法信息列表
        """
        algs = await AlgDao.get_alg_details_by_ids(query_db, alg_ids=alg_ids)
        result = []
        for alg in algs:
            # logger.info(f'{CamelCaseUtil.transform_result(alg)}')
            result.append(CamelCaseUtil.transform_result(alg))
        return result

    @classmethod
    async def add_alg_services(cls, query_db: AsyncSession, alg: AlgModel):
        existing = await AlgDao.get_alg_by_serial_version(query_db, alg.alg_serial, alg.alg_version)
        if existing:
            raise ValueError('该算法版本已存在')
        alg.alg_update_time = datetime.now()
        db_alg = await AlgDao.add_alg_dao(query_db, alg)
        await query_db.commit()
        return db_alg

    @classmethod
    async def edit_alg_services(cls, query_db: AsyncSession, alg: AlgModel):
        """
        编辑算法信息service

        :param query_db: orm对象
        :param alg: 算法对象
        :return:
        """
        update_data = alg.model_dump(exclude_unset=True)
        update_data['alg_update_time'] = datetime.now()
        # 调用DAO层编辑算法
        await AlgDao.edit_alg_dao(query_db, update_data)
        await query_db.commit()

    @classmethod
    async def delete_alg_services(cls, query_db: AsyncSession, alg_id: int):
        """
        删除算法信息service

        :param query_db: orm对象
        :param alg_id: 算法id
        :return:
        """
        # 检查算法是否存在
        alg_info = await AlgDao.get_alg_detail_by_id(query_db, alg_id=alg_id)
        if alg_info:
            video_list = await VideoDao.get_video_all(query_db)
            video_rows = [
                {
                    'vid_id': video[0],
                    'vid_scene_name': video[1],
                    'vid_algorithm_name': video[2],
                    'vid_algorithm': video[3],
                }
                for video in video_list
            ]
            if cls.algorithm_is_bound(video_rows, alg_id):
                raise ValueError('算法版本已绑定摄像头，请先解绑后再删除')
            # 调用DAO层删除算法
            await AlgDao.delete_alg_dao(query_db, alg_id=alg_id)
            await query_db.commit()
            return True
        return False

    @classmethod
    async def get_statistics_services(cls, query_db: AsyncSession):
        """
        获取算法、场景、视频统计信息service

        :param query_db: orm对象
        :return: 统计信息对象
        """
        # 获取算法数量
        alg_count = await AlgDao.get_alg_count(query_db)
        # 获取场景数量
        scene_count = await SceneDao.get_scene_count(query_db)
        # 获取视频数量
        video_count = await VideoDao.get_video_count(query_db)
        # 获取启动视频推流操作数量
        video_stream_count = await IntegrationLogDao.get_video_stream_count(query_db)

        return {
            'algorithm_count': alg_count,
            'scene_count': scene_count,
            'video_count': video_count,
            'video_stream_count': video_stream_count,
        }

    @classmethod
    async def get_charts_services(cls, query_db: AsyncSession):
        """
        获取表格统计信息service

        :param query_db: orm对象
        :return: 表格统计信息对象
        """
        # 获取所有视频信息
        video_list = await VideoDao.get_video_all(query_db)
        video_dict = {}
        for video in video_list:
            video_dict[video[0]] = {
                'vid_id': video[0],
                'vid_scene_name': video[1],
                'vid_algorithm_name': video[2],
            }

        # 获取所有"推送视频配置"操作的信息
        video_stream_list = await IntegrationLogDao.get_video_stream_all(query_db)
        scene_dict = {}
        alg_dict = {}
        for video_stream in video_stream_list:
            try:
                push_request_str = json.loads(video_stream[1]).get('push_request', '')
                # 尝试使用正则提取vid_id
                match = re.search(r'vid_id=(\d+)', push_request_str)
                if match:
                    vid = int(match.group(1))
                else:
                    # 兼容旧逻辑，但增加split处理额外信息
                    # 之前的错误是: invalid literal for int() with base 10: '18 vid_serial=None vid_stream=None'
                    cleaned_str = push_request_str.replace('vid_id=', '').strip()
                    if cleaned_str:
                        vid = int(cleaned_str.split()[0])
                    else:
                        continue
            except Exception as e:
                logger.error(f'获取视频流操作视频id失败，错误信息：{e}')
                continue

            if vid in video_dict:
                scene_name = video_dict[vid].get('vid_scene_name', '')
                alg_name = video_dict[vid].get('vid_algorithm_name', '[]')
                if scene_name:
                    scene_dict.setdefault(scene_name, 0)
                    scene_dict[scene_name] += 1
                if alg_name:
                    for alg in json.loads(alg_name):
                        alg_dict.setdefault(alg, 0)
                        alg_dict[alg] += 1

        # 计算top10
        top10_scene = sorted(scene_dict.items(), key=lambda x: x[1], reverse=True)[:10]
        top10_alg = sorted(alg_dict.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'top10_scene': top10_scene,
            'top10_alg': top10_alg,
        }
