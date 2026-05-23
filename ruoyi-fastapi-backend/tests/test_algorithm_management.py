import unittest
from pathlib import Path

from module_xuzhou.service.alg_service import AlgService
from module_xuzhou.service import face_feature_worker_onnx


class AlgorithmManagementHelperTests(unittest.TestCase):
    def test_safe_path_part_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            AlgService.safe_path_part("../bad")

    def test_safe_path_part_allows_code_version_text(self):
        self.assertEqual("fire_detection-v1", AlgService.safe_path_part("fire_detection-v1"))

    def test_build_weight_relative_path_uses_algorithm_model_directory(self):
        path = AlgService.build_weight_relative_path("fire_detection", "v1", "fire.onnx")
        self.assertEqual("algorithm/model/fire_detection/v1/fire.onnx", path)

    def test_arcface_model_path_uses_algorithm_model_directory(self):
        self.assertEqual(
            Path("algorithm/model/arcface_recognition/v1/w600k_r50.onnx"),
            Path(face_feature_worker_onnx._onnx_model_path).relative_to(face_feature_worker_onnx.BACKEND_ROOT),
        )

    def test_validate_weight_extension_rejects_unknown_extension(self):
        with self.assertRaises(ValueError):
            AlgService.validate_weight_extension("fire.txt")

    def test_algorithm_is_bound_when_vid_algorithm_contains_alg_id(self):
        rows = [
            {"vidAlgorithm": [{"algId": 12, "algVersion": "v1"}]},
            {"vidAlgorithm": []},
        ]
        self.assertTrue(AlgService.algorithm_is_bound(rows, 12))

    def test_algorithm_is_not_bound_when_vid_algorithm_is_empty(self):
        rows = [{"vidAlgorithm": []}, {"vidAlgorithm": None}]
        self.assertFalse(AlgService.algorithm_is_bound(rows, 12))


if __name__ == "__main__":
    unittest.main()
