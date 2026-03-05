import asyncio
import json
from sqlalchemy.ext.asyncio import AsyncSession
from module_xuzhou.dao.scene_dao import SceneDao
from module_xuzhou.entity.vo.scene_vo import SceneModel, ScenePageQueryModel, SceneDetailModel
from module_xuzhou.service.alg_service import AlgService
from utils.common_util import CamelCaseUtil
from utils.log_util import logger


class SceneService:
    """
    场景管理模块服务层
    """

    @classmethod
    async def get_scene_list_services(
        cls, query_db: AsyncSession, query_object: ScenePageQueryModel, is_page: bool = False
    ):
        """
        获取场景列表信息service

        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 场景列表信息对象
        """
        scene_list_result = await SceneDao.get_scene_list(query_db, query_object, is_page)
        if hasattr(scene_list_result, 'rows') and isinstance(scene_list_result.rows, list):
            for item in scene_list_result.rows:
                if 'sceneAlgorithm' in item:
                    item['sceneAlgorithm'] = json.loads(item['sceneAlgorithm'])
                if 'sceneAlgorithmName' in item:
                    item['sceneAlgorithmName'] = json.loads(item['sceneAlgorithmName'])

        return scene_list_result

    @classmethod
    async def scene_detail_services(cls, query_db: AsyncSession, scene_id: int):
        """
        获取场景详细信息service

        :param query_db: orm对象
        :param scene_id: 场景id
        :return: 场景id对应的信息
        """
        scene = await SceneDao.get_scene_detail_by_id(query_db, scene_id=scene_id)
        if scene:
            # 转换场景基本信息
            scene_dict = CamelCaseUtil.transform_result(scene)
            scene_model = SceneModel(**scene_dict)

            # 创建SceneDetailModel实例，确保包含所有场景信息
            scene_detail_dict = scene_model.model_dump()
            scene_detail_dict['alg_details'] = []

            # 如果场景包含算法ID列表，则获取详细的算法信息
            if scene.scene_algorithm:
                # 解析算法ID列表
                try:
                    alg_ids = json.loads(scene.scene_algorithm)

                    # 批量获取算法详细信息
                    alg_details = await AlgService.alg_details_services(query_db, alg_ids)

                    # 将算法详细信息添加到结果中
                    scene_detail_dict['alg_details'] = alg_details
                except (ValueError, AttributeError):
                    # 如果解析算法ID列表失败，忽略错误
                    pass
            # result = SceneDetailModel(**scene_detail_dict)
        else:
            result = SceneDetailModel(**dict())

        return scene_detail_dict

    @classmethod
    async def add_scene_services(cls, query_db: AsyncSession, scene: SceneModel):
        """
        新增场景信息service

        :param query_db: orm对象
        :param scene: 场景对象
        :return: 新增结果
        """
        result = await SceneDao.add_scene_dao(query_db, scene)
        return result

    @classmethod
    async def edit_scene_services(cls, query_db: AsyncSession, scene: SceneModel):
        """
        编辑场景信息service

        :param query_db: orm对象
        :param scene: 场景对象
        :return: 编辑结果
        """
        # 获取旧的场景信息
        scene_info = await SceneDao.get_scene_detail_by_id(query_db, scene_id=scene.scene_id)
        if scene_info:
            # 更新数据
            scene_data = scene.model_dump(exclude_unset=True)
            for key, value in scene_data.items():
                setattr(scene_info, key, value)
            await query_db.commit()
            return True
        else:
            return False

    @classmethod
    async def delete_scene_services(cls, query_db: AsyncSession, scene_id: int):
        """
        删除场景信息service

        :param query_db: orm对象
        :param scene_id: 场景id
        :return: 删除结果
        """
        scene_info = await SceneDao.get_scene_detail_by_id(query_db, scene_id=scene_id)
        if scene_info:
            await SceneDao.delete_scene_dao(query_db, scene_id=scene_id)
            await query_db.commit()
            return True
        else:
            return False
