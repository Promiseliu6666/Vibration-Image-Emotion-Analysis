import asyncio
import base64
import io
import json
import os
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from typing import Any, Optional

# Reduce backend inference logs (set before importing inference libs when possible).
os.environ.setdefault("GLOG_minloglevel", "2")

import numpy as np
import paddle
from PIL import Image
from paddlex import create_model
from sqlalchemy.ext.asyncio import AsyncSession

from module_xuzhou.dao.people_dao import PeopleDao
from module_xuzhou.entity.vo.people_vo import PeopleModel, PeopleModelWithFeatures, PeoplePageQueryModel
from module_xuzhou.error.people_error import InvalidPictureError, PeopleNotFoundError
from utils.common_util import CamelCaseUtil
from utils.log_util import logger

feature_extractor = None

# Lightweight in-memory cache for group vectors.
FEATURE_CACHE_TTL_SECONDS = 30
group_feature_cache: dict[int, dict[str, Any]] = {}
group_feature_cache_lock = asyncio.Lock()

# PaddleX model inference is heavy and not guaranteed to be thread-safe in parallel.
feature_extract_lock = asyncio.Lock()


async def get_feature_extractor():
    global feature_extractor
    if feature_extractor is None:
        feature_extractor = FaceFeatureExtractor()
    return feature_extractor


class PeopleService:
    @classmethod
    async def get_people_list_services(
        cls, query_db: AsyncSession, query_object: PeoplePageQueryModel, is_page: bool = False, include_deleted=False
    ):
        return await PeopleDao.get_people_list(query_db, query_object, is_page, include_deleted)

    @classmethod
    async def people_detail_services(cls, query_db: AsyncSession, people_id: int):
        if people := await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id):
            return PeopleModel(**CamelCaseUtil.transform_result(people))
        return PeopleModel(**dict())

    @classmethod
    async def people_details_services(cls, query_db: AsyncSession, group_id: int, people_ids: list[int]):
        result = []
        for people in await PeopleDao.get_people_details_by_ids(query_db, group_id=group_id, people_ids=people_ids):
            result.append(CamelCaseUtil.transform_result(people))
        return result

    @classmethod
    async def extract_features(cls, image_str: str) -> list:
        extractor: FaceFeatureExtractor = await get_feature_extractor()
        async with feature_extract_lock:
            features: np.ndarray = await asyncio.to_thread(extractor.extract_features, image_str)
        return features.tolist()

    @classmethod
    async def add_people_services(cls, query_db: AsyncSession, people: PeopleModelWithFeatures):
        if people.group_id is None:
            raise ValueError("group_id is required")
        people.created_time = datetime.now()
        people.updated_time = datetime.now()
        people_id = await PeopleDao.add_people_dao(query_db, people)
        await query_db.commit()
        cls._invalidate_feature_cache(people.group_id)
        return people_id

    @classmethod
    async def edit_people_services(cls, query_db: AsyncSession, people: PeopleModel, people_id: int):
        if not (people_detail := await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id)):
            raise PeopleNotFoundError("Member not found")

        old_group_id = people_detail.group_id
        new_group_id = people.group_id if people.group_id is not None else people_detail.group_id

        await PeopleDao.edit_people_dao(
            query_db,
            {
                **people.model_dump(include={"name", "group_id"}),
                **({"features": people.features, "pics": people.pics} if people.pics else {}),
                **{
                    "id": people_detail.id,
                    "group_id": new_group_id,
                    "name": people.name if people.name is not None else people_detail.name,
                    "updated_time": datetime.now(),
                },
            },
        )
        await query_db.commit()
        cls._invalidate_feature_cache(old_group_id)
        cls._invalidate_feature_cache(new_group_id)

    @classmethod
    async def delete_people_services(cls, query_db: AsyncSession, people_id: int):
        if people_detail := await PeopleDao.get_people_detail_by_id(query_db, people_id=people_id):
            # AsyncSession defaults to expiring ORM state on commit; keep scalar values
            # before commit to avoid implicit refresh (which can raise MissingGreenlet).
            group_id = people_detail.group_id
            await PeopleDao.delete_people_dao(query_db, people_id=people_id)
            await query_db.commit()
            cls._invalidate_feature_cache(group_id)
            return True
        return False

    @classmethod
    def _invalidate_feature_cache(cls, group_id: Optional[int] = None):
        if group_id is None:
            group_feature_cache.clear()
            return
        group_feature_cache.pop(group_id, None)

    @classmethod
    def _to_normalized_feature_vector(cls, features: Any) -> Optional[np.ndarray]:
        try:
            if isinstance(features, np.ndarray):
                raw_features = features
            elif isinstance(features, str):
                raw_features = json.loads(features)
            elif isinstance(features, list):
                raw_features = features
            else:
                return None
            vector = np.asarray(raw_features, dtype=np.float32).reshape(-1)
            norm = np.linalg.norm(vector)
            if norm <= 0:
                return None
            return vector / norm
        except (json.JSONDecodeError, ValueError, TypeError):
            return None

    @classmethod
    async def _get_group_feature_vectors(cls, query_db: AsyncSession, group_id: int) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = group_feature_cache.get(group_id)
        if cached and now - cached.get("ts", 0) < FEATURE_CACHE_TTL_SECONDS:
            return cached.get("items", [])

        async with group_feature_cache_lock:
            cached = group_feature_cache.get(group_id)
            now = time.monotonic()
            if cached and now - cached.get("ts", 0) < FEATURE_CACHE_TTL_SECONDS:
                return cached.get("items", [])

            all_people = await PeopleDao.get_people_features_by_group(query_db, group_id)
            items: list[dict[str, Any]] = []
            for person in all_people:
                vector = cls._to_normalized_feature_vector(person.features)
                if vector is None:
                    continue
                items.append(
                    {
                        "id": person.id,
                        "name": person.name,
                        "group_id": person.group_id,
                        "pics": person.pics,
                        "vector": vector,
                    }
                )
            group_feature_cache[group_id] = {"ts": now, "items": items}
            return items

    @classmethod
    async def face_compare_services(
        cls, query_db: AsyncSession, image_str: str, group_id: int, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """
        Face compare service.
        """
        try:
            extractor: FaceFeatureExtractor = await get_feature_extractor()
            async with feature_extract_lock:
                upload_features_raw: np.ndarray = await asyncio.to_thread(extractor.extract_features, image_str)
            upload_features = cls._to_normalized_feature_vector(upload_features_raw)
            if upload_features is None:
                return [{}]

            all_people = await cls._get_group_feature_vectors(query_db, group_id)
            results: list[dict[str, Any]] = []
            for person in all_people:
                person_vector = person.get("vector")
                if person_vector is None:
                    continue
                try:
                    similarity = float(np.dot(upload_features, person_vector))
                except ValueError:
                    continue
                if similarity >= threshold:
                    results.append(
                        {
                            "id": person["id"],
                            "name": person["name"],
                            "group_id": person["group_id"],
                            "similarity": round(similarity, 4),
                            "pics": person["pics"],
                        }
                    )

            results.sort(key=lambda x: x["similarity"], reverse=True)
            logger.info(f"Face compare finished, matched count={len(results)}")
            return results if results else [{}]
        except InvalidPictureError as e:
            # Expected in real-time streams (occlusion / blur / no face).
            logger.debug(f"Face compare skipped: {e}")
            return [{}]
        except Exception as e:
            logger.error(f"Face compare failed: {e}")
            logger.error(traceback.format_exc())
            return [{}]

    @staticmethod
    def _calculate_cosine_similarity(features1: np.ndarray, features2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two feature vectors.
        """
        features1 = np.array(features1, dtype=np.float32)
        features2 = np.array(features2, dtype=np.float32)

        norm1 = np.linalg.norm(features1)
        norm2 = np.linalg.norm(features2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        similarity = np.dot(features1, features2) / (norm1 * norm2)
        return float(similarity)

    @classmethod
    async def face_compare_by_face_crop_services(
        cls, query_db: AsyncSession, face_crop: np.ndarray, group_id: int, threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Face compare using pre-cropped face image (no detection step)."""
        try:
            extractor: FaceFeatureExtractor = await get_feature_extractor()
            async with feature_extract_lock:
                features_raw: np.ndarray = await asyncio.to_thread(
                    extractor.extract_features_from_crop, face_crop
                )
            upload_features = cls._to_normalized_feature_vector(features_raw)
            if upload_features is None:
                return [{}]

            all_people = await cls._get_group_feature_vectors(query_db, group_id)
            results: list[dict[str, Any]] = []
            for person in all_people:
                person_vector = person.get("vector")
                if person_vector is None:
                    continue
                try:
                    similarity = float(np.dot(upload_features, person_vector))
                except ValueError:
                    continue
                if similarity >= threshold:
                    results.append({
                        "id": person["id"],
                        "name": person["name"],
                        "group_id": person["group_id"],
                        "similarity": round(similarity, 4),
                        "pics": person["pics"],
                    })

            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results if results else [{}]
        except InvalidPictureError as e:
            logger.debug(f"Face compare by crop skipped: {e}")
            return [{}]
        except Exception as e:
            logger.error(f"Face compare by crop failed: {e}")
            logger.error(traceback.format_exc())
            return [{}]


class FaceFeatureExtractor:
    """Face feature extractor."""

    def __init__(self):
        # Suppress noisy model-init stdout text like:
        # "Model files already exist. Using cached files..."
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.face_detect_model = create_model(model_name="PP-YOLOE_plus-S_face")
            self.extract_feature_model = create_model(model_name="ResNet50_face")

    @classmethod
    def _prepare_image(cls, base64_string: str) -> np.ndarray:
        if "," in base64_string:
            base64_string = base64_string.split(",", 1)[1]
        base64_string = base64_string.strip()
        image_data = base64.b64decode(base64_string)
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        return np.array(image)

    def _detect_person(self, base64_string: str) -> np.ndarray:
        image_np: np.ndarray = self._prepare_image(base64_string)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            results: list = list(self.face_detect_model.predict(image_np))
        if len(results) == 0:
            raise InvalidPictureError("No face recognized")

        boxes: list[dict] = results[0]["boxes"]
        if len(boxes) == 0:
            raise InvalidPictureError("No face detected")

        largest_box = None
        largest_area = 0
        for box in boxes:
            x1, y1, x2, y2 = map(int, box["coordinate"])
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(image_np.shape[1], x2)
            y2 = min(image_np.shape[0], y2)
            if x2 > x1 and y2 > y1:
                area = (x2 - x1) * (y2 - y1)
                if area > largest_area:
                    largest_area = area
                    largest_box = (x1, y1, x2, y2)

        if largest_box is None:
            raise InvalidPictureError("No valid face area found")

        x1, y1, x2, y2 = largest_box
        return image_np[y1:y2, x1:x2]

    def extract_large_features(self, base64_string: str) -> np.ndarray:
        image_np: np.ndarray = self._prepare_image(base64_string)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            results: list = list(self.face_detect_model.predict(image_np))

        if len(results) != 1:
            raise InvalidPictureError("Face detection failed")

        boxes: list[dict] = results[0]["boxes"]
        if len(boxes) == 0:
            raise InvalidPictureError("No face detected")

        largest_box = None
        largest_area = 0
        for box in boxes:
            x1, y1, x2, y2 = map(int, box["coordinate"])
            x1, y1 = max(0, x1), max(0, y1)
            x2 = min(image_np.shape[1], x2)
            y2 = min(image_np.shape[0], y2)
            if x2 > x1 and y2 > y1:
                area = (x2 - x1) * (y2 - y1)
                if area > largest_area:
                    largest_area = area
                    largest_box = (x1, y1, x2, y2)

        if largest_box is None:
            raise InvalidPictureError("No valid face area found")

        x1, y1, x2, y2 = largest_box
        cropped: np.ndarray = image_np[y1:y2, x1:x2]
        with paddle.no_grad(), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            features: list = list(self.extract_feature_model.predict(cropped))

        if len(features) != 1:
            raise InvalidPictureError("Feature extraction failed")
        return list(features)[0]["feature"]

    def extract_features(self, base64_string: str) -> np.ndarray:
        image_np: np.ndarray = self._detect_person(base64_string)
        with paddle.no_grad(), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            features: list = list(self.extract_feature_model.predict(image_np))
        if len(features) == 0:
            raise InvalidPictureError("No face recognized")
        return list(features)[0]["feature"]

    def extract_features_from_crop(self, face_crop: np.ndarray) -> np.ndarray:
        """Extract features from a pre-cropped face image (no detection needed)."""
        with paddle.no_grad(), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            features: list = list(self.extract_feature_model.predict(face_crop))
        if len(features) == 0:
            raise InvalidPictureError("Face feature extraction failed")
        return list(features)[0]["feature"]
