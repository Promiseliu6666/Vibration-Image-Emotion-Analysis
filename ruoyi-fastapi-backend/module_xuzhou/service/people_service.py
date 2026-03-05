import base64
import io
import json
import traceback
from datetime import datetime
from typing import Dict, Any

import numpy as np
import paddle
from PIL import Image
from paddlex import create_model
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.people_dao import PeopleDao
from module_xuzhou.entity.vo.people_vo import PeopleModel, PeoplePageQueryModel, PeopleModelWithFeatures
from module_xuzhou.error.people_error import PeopleNotFoundError, InvalidPictureError
from utils.common_util import CamelCaseUtil
from utils.log_util import logger

feature_extractor = None


async def get_feature_extractor():
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = FaceFeatureExtractor()
    return feature_extractor


class PeopleService:
    @classmethod
    async def get_people_list_services(
            cls, query_db: AsyncSession, query_object: PeoplePageQueryModel, is_page: bool = False,
            include_deleted=False
    ):
        people_list_result = await PeopleDao.get_people_list(query_db, query_object, is_page, include_deleted)
        return people_list_result

    @classmethod
    async def people_detail_services(cls, query_db: AsyncSession, people_id: int):
        if people := await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id):
            result = PeopleModel(**CamelCaseUtil.transform_result(people))
        else:
            result = PeopleModel(**dict())
        return result

    @classmethod
    async def people_details_services(cls, query_db: AsyncSession, group_id: int, people_ids: list[int]):
        result = []
        for people in await PeopleDao.get_people_details_by_ids(query_db, group_id=group_id, people_ids=people_ids):
            result.append(CamelCaseUtil.transform_result(people))
        return result

    @classmethod
    async def extract_features(cls, image_str: str) -> list:
        extractor: FaceFeatureExtractor = await get_feature_extractor()
        features: np.ndarray = extractor.extract_features(image_str)
        return features.tolist()

    @classmethod
    async def add_people_services(cls, query_db: AsyncSession, people: PeopleModelWithFeatures):
        people.created_time = datetime.now()
        people.updated_time = datetime.now()
        people_id = await PeopleDao.add_people_dao(query_db, people)
        await query_db.commit()
        return people_id

    @classmethod
    async def edit_people_services(cls, query_db: AsyncSession, people: PeopleModel, people_id: int):
        if not (people_detail := await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id)):
            raise PeopleNotFoundError('成员不存在')
        await PeopleDao.edit_people_dao(
            query_db,
            {
                **people.model_dump(include={'name', 'group_id'}),
                **({'features': people.features, 'pics': people.pics} if people.pics else {}),
                **{
                    'id': people_detail.id,
                    'group_id': people.group_id if people.group_id is not None else people_detail.group_id,
                    'name': people.name if people.name is not None else people_detail.name,
                    'updated_time': datetime.now(),
                },
            },
        )
        await query_db.commit()

    @classmethod
    async def delete_people_services(cls, query_db: AsyncSession, people_id: int):
        if await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id):
            await PeopleDao.delete_people_dao(query_db, people_id=people_id)
            await query_db.commit()
            return True
        return False

    @classmethod
    async def face_compare_services(
            cls, query_db: AsyncSession, image_str: str, group_id: int, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """
        人脸比对服务

        Args:
            query_db: 数据库会话
            image_str: base64编码的图像字符串
            group_id: 组 id
            threshold: 相似度阈值，默认0.7

        Returns:
            Dict: 匹配结果列表，包含人员信息和相似度
        """
        try:
            # 提取上传图片的特征
            extractor: FaceFeatureExtractor = await get_feature_extractor()
            upload_features: np.ndarray = extractor.extract_features(image_str)

            # 获取所有人员的特征数据
            all_people = await PeopleDao.get_all_people_features(query_db)

            results = []
            for person in all_people:
                if person.group_id != group_id:
                    continue
                if person.features:
                    try:
                        # 解析存储的特征数据，处理不同的数据类型
                        if isinstance(person.features, str):
                            stored_features = json.loads(person.features)
                        elif isinstance(person.features, list):
                            stored_features = person.features
                        else:
                            # 跳过不支持的数据类型
                            continue

                        stored_features_array = np.array(stored_features)

                        # 计算余弦相似度
                        similarity = cls._calculate_cosine_similarity(upload_features, stored_features_array)

                        # 如果相似度超过阈值，添加到结果中
                        if similarity >= threshold:
                            results.append(
                                {
                                    'id': person.id,
                                    'name': person.name,
                                    'group_id': person.group_id,
                                    'similarity': round(similarity, 4),
                                    'pics': person.pics,
                                }
                            )
                    except (json.JSONDecodeError, ValueError, TypeError) as e:
                        # 跳过无法解析的特征数据
                        logger.warning(f'跳过人员 {person.id} 的特征数据，解析错误: {e}')
                        continue

            # 按相似度降序排序
            results.sort(key=lambda x: x['similarity'], reverse=True)

            logger.info(f'人脸比对完成，找到 {len(results)} 个匹配结果')
            if results:
                return results
            else:
                return [{}]

        except Exception as e:
            logger.error(f'人脸比对服务异常: {e}')
            logger.error(traceback.format_exc())
            return [{}]

    @staticmethod
    def _calculate_cosine_similarity(features1: np.ndarray, features2: np.ndarray) -> float:
        """
        计算两个特征向量的余弦相似度

        Args:
            features1: 第一个特征向量
            features2: 第二个特征向量

        Returns:
            float: 余弦相似度值 (-1到1之间，但通常在0-1之间)
        """
        # 确保输入是numpy数组
        features1 = np.array(features1, dtype=np.float32)
        features2 = np.array(features2, dtype=np.float32)

        # 计算向量的模长
        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)

        # 避免除零错误
        if norm1 == 0 or norm2 == 0:
            return 0.0

        # 计算向量的点积
        dot_product = np.dot(features1, features2)
        norm_extracted = np.linalg.norm(features1)
        norm_db = np.linalg.norm(features2)

        # 计算余弦相似度
        if norm_extracted > 0 and norm_db > 0:
            similarity = dot_product / (norm_extracted * norm_db)
        else:
            similarity = 0.0

        # 可选：添加调试信息（生产环境中应移除）
        # print(f"余弦相似度={similarity:.4f}, 欧几里得距离={np.linalg.norm(features1 - features2):.4f}")

        # 余弦相似度的范围是-1到1，但对于人脸特征通常在0-1之间
        return float(similarity)


class FaceFeatureExtractor:
    """人脸特征提取"""

    def __init__(self):
        self.face_detect_model = create_model(model_name='PP-YOLOE_plus-S_face')
        self.extract_feature_model = create_model(model_name='ResNet50_face')

    @classmethod
    def _prepare_image(cls, base64_string: str) -> np.ndarray:
        # 处理可能存在的数据URI前缀
        if ',' in base64_string:
            base64_string = base64_string.split(',', 1)[1]

        # 清理可能存在的空白字符
        base64_string = base64_string.strip()

        # 解码base64字符串并打开图像
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        return np.array(image)  # RGB format, HWC

    def _detect_person(self, base64_string: str) -> np.ndarray:
        image_np: np.ndarray = self._prepare_image(base64_string)

        # 人脸检测
        results: list = list(self.face_detect_model.predict(image_np))
        if len(results) == 0:
            raise InvalidPictureError('无法识别人脸')

        boxes: list[dict] = results[0]['boxes']
        if len(boxes) == 0:
            raise InvalidPictureError('未检测到人脸')

        # 找到面积最大的人脸框
        largest_box = None
        largest_area = 0

        for box in boxes:
            x1, y1, x2, y2 = map(int, box['coordinate'])
            # 确保坐标有效
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(image_np.shape[1], x2)
            y2 = min(image_np.shape[0], y2)

            if x2 > x1 and y2 > y1:
                area = (x2 - x1) * (y2 - y1)
                if area > largest_area:
                    largest_area = area
                    largest_box = (x1, y1, x2, y2)

        if largest_box is None:
            raise InvalidPictureError('无法找到有效的人脸区域')

        # 裁剪最大的人脸区域
        x1, y1, x2, y2 = largest_box
        cropped: np.ndarray = image_np[y1:y2, x1:x2]
        return cropped

    def extract_large_features(self, base64_string: str) -> np.ndarray:
        """输出最大人脸的特征向量

        Args:
            base64_string (str): base64编码的图像字符串

        Returns:
            np.ndarray: 最大人脸的特征向量

        Raises:
            InvalidPictureError: 当无法检测到人脸时抛出
        """
        image_np: np.ndarray = self._prepare_image(base64_string)
        results: list = list(self.face_detect_model.predict(image_np))

        if len(results) != 1:
            raise InvalidPictureError('人脸检测失败')

        boxes: list[dict] = results[0]['boxes']
        if len(boxes) == 0:
            raise InvalidPictureError('未检测到人脸')

        # 找到面积最大的人脸框
        largest_box = None
        largest_area = 0

        for box in boxes:
            x1, y1, x2, y2 = map(int, box['coordinate'])
            # 确保坐标有效
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(image_np.shape[1], x2)
            y2 = min(image_np.shape[0], y2)

            if x2 > x1 and y2 > y1:
                area = (x2 - x1) * (y2 - y1)
                if area > largest_area:
                    largest_area = area
                    largest_box = (x1, y1, x2, y2)

        if largest_box is None:
            raise InvalidPictureError('无法找到有效的人脸区域')

        # 裁剪最大的人脸区域
        x1, y1, x2, y2 = largest_box
        cropped: np.ndarray = image_np[y1:y2, x1:x2]

        # 提取特征向量
        with paddle.no_grad():
            features: list = list(self.extract_feature_model.predict(cropped))

        if len(features) != 1:
            raise InvalidPictureError('特征提取失败')

        result_dict: dict = list(features)[0]
        return result_dict['feature']

    def extract_features(self, base64_string: str) -> np.ndarray:
        """
        从base64编码的图像中提取特征向量

        Args:
            base64_string (str): base64编码的图像字符串

        Returns:
            numpy.ndarray: 特征向量
        """
        image_np: np.ndarray = self._detect_person(base64_string)
        with paddle.no_grad():
            features: list = list(self.extract_feature_model.predict(image_np))

        if len(features) == 0:
            raise InvalidPictureError('无法识别人脸')

        result_dict: dict = list(features)[0]
        return result_dict['feature']
