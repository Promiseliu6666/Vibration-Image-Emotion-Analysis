"""
One-time script: re-extract face feature vectors for ALL people using the
current ArcFace w600k_r50 ONNX model.

The DB may contain vectors from the old PaddleX model. This script updates
them so the box's ArcFace embeddings can match locally.

Usage:
    cd ruoyi-fastapi-backend && uv run python scripts/re_extract_all_features.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.database import AsyncSessionLocal
from module_xuzhou.dao.people_dao import PeopleDao
from module_xuzhou.service.people_service import PeopleService, get_feature_extractor


async def main():
    print("Loading ArcFace model (first time may take a minute)...")
    extractor = await get_feature_extractor()
    print("Model loaded.")

    async with AsyncSessionLocal() as db:
        all_people = await PeopleDao.get_all_people_features(db)
        print(f"Found {len(all_people)} people in database")

        updated = 0
        skipped = 0
        for person in all_people:
            if not person.pics:
                print(f"  SKIP person_id={person.id} name={person.name}: no pics (original photo)")
                skipped += 1
                continue

            try:
                features = await PeopleService.extract_features(person.pics)
                features_json = json.dumps(features)
                await PeopleDao.edit_people_dao(
                    db,
                    {"id": person.id, "features": features_json},
                )
                print(f"  OK   person_id={person.id} name={person.name} dim={len(features)}")
                updated += 1
            except Exception as e:
                print(f"  FAIL person_id={person.id} name={person.name}: {e}")
                skipped += 1

        await db.commit()
        print(f"\nDone: {updated} updated, {skipped} skipped, {len(all_people)} total")


if __name__ == "__main__":
    asyncio.run(main())
