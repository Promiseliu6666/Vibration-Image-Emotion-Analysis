# Algorithm Decoupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build database-managed algorithm versions with disk-based weight uploads, frontend algorithm management, and camera binding to specific algorithm versions.

**Architecture:** Reuse the existing `xuzhou_alg` table as the algorithm-version catalog and add fields for weight path and enabled status. Store uploaded model files under `ruoyi-fastapi-backend/algorithm/weights/{alg_serial}/{alg_version}/`, while camera bindings continue to use the existing `vidAlgorithm` JSON field but now store full version objects. Runtime resolution validates enabled/version/weight information before starting local or external algorithms.

**Tech Stack:** FastAPI, async SQLAlchemy, Pydantic, Vue 3, Element Plus, Axios, existing RuoYi pagination and response helpers.

---

## File Structure

Backend files to modify:
- `ruoyi-fastapi-backend/module_xuzhou/entity/do/alg_do.py` — add algorithm weight path and enabled status columns.
- `ruoyi-fastapi-backend/module_xuzhou/entity/vo/alg_vo.py` — expose new fields and add upload response/request-compatible model fields.
- `ruoyi-fastapi-backend/module_xuzhou/dao/alg_dao.py` — add duplicate lookup, enabled lookup, and safer update behavior.
- `ruoyi-fastapi-backend/module_xuzhou/service/alg_service.py` — validate duplicates, upload files, reject deletion when bound, normalize default config.
- `ruoyi-fastapi-backend/module_xuzhou/controller/algorithm_controller.py` — add multipart upload endpoint and expose new CRUD fields.
- `ruoyi-fastapi-backend/algorithm/runtime_service.py` — resolve full version objects and include weight/config params.
- `ruoyi-fastapi-backend/tests/test_multi_camera_analysis.py` — extend runtime tests.
- `ruoyi-fastapi-backend/tests/test_algorithm_management.py` — create service-level tests for upload path, duplicate version, and deletion guard.

Frontend files to modify:
- `ruoyi-fastapi-frontend/src/api/xuzhou/algorithm.js` — add upload API and enable/disable/edit helpers if missing.
- `ruoyi-fastapi-frontend/src/views/algorithm/list/index.vue` — full algorithm/version management, weight upload, enabled status, version-aware camera binding.

---

### Task 1: Add Algorithm Version Fields

**Files:**
- Modify: `ruoyi-fastapi-backend/module_xuzhou/entity/do/alg_do.py`
- Modify: `ruoyi-fastapi-backend/module_xuzhou/entity/vo/alg_vo.py`
- Test: `ruoyi-fastapi-backend/tests/test_multi_camera_analysis.py`

- [ ] **Step 1: Write the failing model test**

Append this test to `AlgorithmRuntimeServiceTests` in `ruoyi-fastapi-backend/tests/test_multi_camera_analysis.py`:

```python
    def test_external_box_binding_includes_version_weight_and_default_conf(self):
        video_detail = {
            "vid_id": 2,
            "vid_algorithm": [
                {
                    "algId": 9,
                    "algName": "烟火检测",
                    "algSerial": "fire_detection",
                    "algVersion": "v1",
                    "algWeightPath": "algorithm/weights/fire_detection/v1/fire.onnx",
                    "algDefaultConf": {"threshold": 0.6},
                }
            ],
        }

        bindings = AlgorithmRuntimeService.resolve_camera_algorithms(video_detail)

        self.assertEqual(1, len(bindings))
        self.assertEqual("fire_detection", bindings[0].algorithm_code)
        self.assertEqual("v1", bindings[0].params["alg_version"])
        self.assertEqual("algorithm/weights/fire_detection/v1/fire.onnx", bindings[0].params["weight_path"])
        self.assertEqual({"threshold": 0.6}, bindings[0].params["default_conf"])
        self.assertEqual(9, bindings[0].params["alg_id"])
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: FAIL because `params` does not include `alg_version`, `weight_path`, `default_conf`, and `alg_id`.

- [ ] **Step 3: Add database columns**

Modify `ruoyi-fastapi-backend/module_xuzhou/entity/do/alg_do.py` so imports and class fields include:

```python
from sqlalchemy import Boolean, Column, DateTime, Integer, String
```

Inside `XuzhouAlg`, after `alg_default_conf` add:

```python
    alg_weight_path = Column(String(500), nullable=True, default=None, comment='算法权重文件路径')
    alg_enabled = Column(Boolean, nullable=False, default=True, comment='是否启用')
```

- [ ] **Step 4: Add Pydantic fields**

Modify `ruoyi-fastapi-backend/module_xuzhou/entity/vo/alg_vo.py` and add to `AlgModel` after `alg_default_conf`:

```python
    alg_weight_path: Optional[str] = Field(default=None, description='算法权重文件路径')
    alg_enabled: bool = Field(default=True, description='是否启用')
```

- [ ] **Step 5: Run syntax verification**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python -m compileall module_xuzhou/entity/do/alg_do.py module_xuzhou/entity/vo/alg_vo.py
```

Expected: command exits 0.

---

### Task 2: Extend Runtime Binding Params

**Files:**
- Modify: `ruoyi-fastapi-backend/algorithm/runtime_service.py:124-154`
- Test: `ruoyi-fastapi-backend/tests/test_multi_camera_analysis.py`

- [ ] **Step 1: Confirm the failing test from Task 1 is red**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: the new runtime params test fails.

- [ ] **Step 2: Update runtime param parsing**

In `AlgorithmRuntimeService.resolve_camera_algorithms`, replace:

```python
            params = cls._parse_params(legacy_algorithm.get("params", legacy_algorithm.get("algDefaultConf", {})))
```

with:

```python
            default_conf = cls._parse_params(legacy_algorithm.get("params", legacy_algorithm.get("algDefaultConf", {})))
            params = {
                "alg_id": legacy_algorithm.get("algId") or legacy_algorithm.get("alg_id"),
                "alg_version": legacy_algorithm.get("algVersion") or legacy_algorithm.get("alg_version"),
                "weight_path": legacy_algorithm.get("algWeightPath") or legacy_algorithm.get("alg_weight_path"),
                "default_conf": default_conf,
            }
```

Keep the existing `algorithm_code` selection logic and `create_external_box_binding(...)` call unchanged except for passing the new `params` variable.

- [ ] **Step 3: Run the runtime tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
```

Expected: all tests in the file pass.

---

### Task 3: Add Algorithm DAO Queries

**Files:**
- Modify: `ruoyi-fastapi-backend/module_xuzhou/dao/alg_dao.py`
- Test: `ruoyi-fastapi-backend/tests/test_algorithm_management.py`

- [ ] **Step 1: Create a failing unit test for duplicate lookup shape**

Create `ruoyi-fastapi-backend/tests/test_algorithm_management.py` with:

```python
import unittest

from module_xuzhou.service.alg_service import AlgService


class AlgorithmManagementHelperTests(unittest.TestCase):
    def test_safe_path_part_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            AlgService.safe_path_part("../bad")

    def test_safe_path_part_allows_code_version_text(self):
        self.assertEqual("fire_detection-v1", AlgService.safe_path_part("fire_detection-v1"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: FAIL because `AlgService.safe_path_part` does not exist.

- [ ] **Step 3: Add DAO helpers**

Add these methods to `AlgDao` in `ruoyi-fastapi-backend/module_xuzhou/dao/alg_dao.py`:

```python
    @classmethod
    async def get_alg_by_serial_version(cls, db: AsyncSession, alg_serial: str, alg_version: str):
        return (
            await db.execute(
                select(XuzhouAlg).where(
                    XuzhouAlg.alg_serial == alg_serial,
                    XuzhouAlg.alg_version == alg_version,
                )
            )
        ).scalars().first()

    @classmethod
    async def get_enabled_alg_by_id(cls, db: AsyncSession, alg_id: int):
        return (
            await db.execute(
                select(XuzhouAlg).where(
                    XuzhouAlg.alg_id == alg_id,
                    XuzhouAlg.alg_enabled == True,
                )
            )
        ).scalars().first()
```

- [ ] **Step 4: Make update target explicit**

Replace `edit_alg_dao` implementation:

```python
        await db.execute(update(XuzhouAlg), [alg])
```

with:

```python
        alg_id = alg.pop('alg_id')
        await db.execute(
            update(XuzhouAlg)
            .where(XuzhouAlg.alg_id == alg_id)
            .values(alg)
        )
```

- [ ] **Step 5: Add service path sanitizer**

Add these imports to `ruoyi-fastapi-backend/module_xuzhou/service/alg_service.py`:

```python
from pathlib import Path
```

Add this method inside `AlgService`:

```python
    @staticmethod
    def safe_path_part(value: str) -> str:
        if not value:
            raise ValueError('路径片段不能为空')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', value):
            raise ValueError('路径片段只能包含字母、数字、下划线、短横线和点')
        return value
```

- [ ] **Step 6: Run the new helper test**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: PASS.

---

### Task 4: Implement Weight Upload Service

**Files:**
- Modify: `ruoyi-fastapi-backend/module_xuzhou/service/alg_service.py`
- Modify: `ruoyi-fastapi-backend/module_xuzhou/controller/algorithm_controller.py`
- Test: `ruoyi-fastapi-backend/tests/test_algorithm_management.py`

- [ ] **Step 1: Add failing tests for extension and path builder**

Append to `AlgorithmManagementHelperTests`:

```python
    def test_build_weight_relative_path_uses_algorithm_weights(self):
        path = AlgService.build_weight_relative_path("fire_detection", "v1", "fire.onnx")
        self.assertEqual("algorithm/weights/fire_detection/v1/fire.onnx", path)

    def test_validate_weight_extension_rejects_unknown_extension(self):
        with self.assertRaises(ValueError):
            AlgService.validate_weight_extension("fire.txt")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: FAIL because `build_weight_relative_path` and `validate_weight_extension` do not exist.

- [ ] **Step 3: Add upload helper constants and methods**

In `AlgService`, add:

```python
    WEIGHT_ROOT = Path('algorithm') / 'weights'
    ALLOWED_WEIGHT_EXTENSIONS = {'.onnx', '.pt', '.pth', '.bin', '.engine'}

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
```

- [ ] **Step 4: Add upload service method**

Add this method inside `AlgService`:

```python
    @classmethod
    async def upload_weight_services(cls, query_db: AsyncSession, alg_name: str, alg_serial: str, alg_version: str, alg_default_conf: str | None, upload_file):
        existing = await AlgDao.get_alg_by_serial_version(query_db, alg_serial, alg_version)
        if existing:
            raise ValueError('该算法版本已存在')

        relative_path = cls.build_weight_relative_path(alg_serial, alg_version, upload_file.filename)
        full_path = Path(relative_path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        content = await upload_file.read()
        full_path.write_bytes(content)

        alg = AlgModel(
            alg_name=alg_name,
            alg_serial=alg_serial,
            alg_version=alg_version,
            alg_default_conf=alg_default_conf or '{}',
            alg_weight_path=relative_path,
            alg_enabled=True,
            alg_update_time=datetime.now(),
        )
        db_alg = await AlgDao.add_alg_dao(query_db, alg)
        await query_db.commit()
        return db_alg
```

- [ ] **Step 5: Add controller upload endpoint**

Modify imports in `algorithm_controller.py`:

```python
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
```

Add endpoint before `/{alg_id}` route:

```python
@algorithmController.post('/upload-weight', summary='上传算法权重并创建版本')
@integration_log(
    title='上传算法权重',
    system_name='徐州算法管理系统',
    business_type=BusinessType.INSERT,
)
async def upload_algorithm_weight(
    request: Request,
    alg_name: str = Form(...),
    alg_serial: str = Form(...),
    alg_version: str = Form(...),
    alg_default_conf: str = Form('{}'),
    file: UploadFile = File(...),
    query_db: AsyncSession = Depends(get_db),
):
    try:
        db_alg = await AlgService.upload_weight_services(
            query_db,
            alg_name=alg_name,
            alg_serial=alg_serial,
            alg_version=alg_version,
            alg_default_conf=alg_default_conf,
            upload_file=file,
        )
        return ResponseUtil.success(data=AlgModel.model_validate(db_alg).model_dump(by_alias=True), msg='上传成功')
    except Exception as e:
        await query_db.rollback()
        return ResponseUtil.error(msg=f'上传失败: {e}')
```

- [ ] **Step 6: Run backend syntax verification**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python -m compileall module_xuzhou/service/alg_service.py module_xuzhou/controller/algorithm_controller.py
```

Expected: command exits 0.

- [ ] **Step 7: Run helper tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: PASS.

---

### Task 5: Reject Deleting Bound Algorithm Versions

**Files:**
- Modify: `ruoyi-fastapi-backend/module_xuzhou/service/alg_service.py`
- Uses: `ruoyi-fastapi-backend/module_xuzhou/dao/video_dao.py`
- Test: `ruoyi-fastapi-backend/tests/test_algorithm_management.py`

- [ ] **Step 1: Add pure helper test for binding detection**

Append to `AlgorithmManagementHelperTests`:

```python
    def test_algorithm_is_bound_when_vid_algorithm_contains_alg_id(self):
        rows = [
            {"vidAlgorithm": [{"algId": 12, "algVersion": "v1"}]},
            {"vidAlgorithm": []},
        ]
        self.assertTrue(AlgService.algorithm_is_bound(rows, 12))

    def test_algorithm_is_not_bound_when_vid_algorithm_is_empty(self):
        rows = [{"vidAlgorithm": []}, {"vidAlgorithm": None}]
        self.assertFalse(AlgService.algorithm_is_bound(rows, 12))
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: FAIL because `algorithm_is_bound` does not exist.

- [ ] **Step 3: Add binding helper**

Add to `AlgService`:

```python
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
```

- [ ] **Step 4: Use helper in delete service**

In `delete_alg_services`, before `await AlgDao.delete_alg_dao(...)`, add:

```python
            video_list = await VideoDao.get_video_all(query_db)
            video_rows = [CamelCaseUtil.transform_result(video) if not isinstance(video, dict) else video for video in video_list]
            if cls.algorithm_is_bound(video_rows, alg_id):
                raise ValueError('算法版本已绑定摄像头，请先解绑后再删除')
```

If `VideoDao.get_video_all` returns tuples in this repository, replace this block with the available video list method that returns dictionaries. The binding helper must still be used with dictionaries containing `vidAlgorithm`.

- [ ] **Step 5: Run helper tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: PASS.

---

### Task 6: Update Frontend API Wrapper

**Files:**
- Modify: `ruoyi-fastapi-frontend/src/api/xuzhou/algorithm.js`

- [ ] **Step 1: Add upload wrapper**

Add this function:

```javascript
export function uploadAlgorithmWeight(data, onUploadProgress) {
  return request({
    url: '/xuzhou/algorithm/upload-weight',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress
  })
}
```

- [ ] **Step 2: Ensure default export includes upload function if file has a default export**

If the file exports a default object, add `uploadAlgorithmWeight` to it.

- [ ] **Step 3: Verify frontend module syntax by building later in Task 8**

No separate command is needed here because Vite build in Task 8 verifies imports.

---

### Task 7: Upgrade Algorithm Management UI

**Files:**
- Modify: `ruoyi-fastapi-frontend/src/views/algorithm/list/index.vue`

- [ ] **Step 1: Update imports**

Change API import to include upload and update:

```javascript
import { listAlgorithm, delAlgorithm, addAlgorithm, updateAlgorithm, uploadAlgorithmWeight } from '@/api/xuzhou/algorithm'
```

- [ ] **Step 2: Add table columns**

Add columns after algorithm version:

```vue
<el-table-column label="权重文件" align="center" prop="algWeightPath" :show-overflow-tooltip="true" />
<el-table-column label="状态" align="center" prop="algEnabled" width="100">
  <template #default="scope">
    <el-tag :type="scope.row.algEnabled ? 'success' : 'info'">
      {{ scope.row.algEnabled ? '启用' : '停用' }}
    </el-tag>
  </template>
</el-table-column>
```

- [ ] **Step 3: Add toolbar buttons**

Inside the `<el-row>` before `<right-toolbar>` add:

```vue
<el-col :span="1.5">
  <el-button type="primary" plain icon="Plus" @click="openEditDialog()">新增算法</el-button>
</el-col>
<el-col :span="1.5">
  <el-button type="success" plain icon="Upload" @click="openUploadDialog">上传权重版本</el-button>
</el-col>
```

- [ ] **Step 4: Add edit dialog**

Add before the existing bind dialog:

```vue
<el-dialog v-model="editDialogVisible" :title="editForm.algId ? '编辑算法' : '新增算法'" width="620px" destroy-on-close>
  <el-form :model="editForm" label-width="110px">
    <el-form-item label="算法名称"><el-input v-model="editForm.algName" /></el-form-item>
    <el-form-item label="算法编号"><el-input v-model="editForm.algSerial" /></el-form-item>
    <el-form-item label="算法版本"><el-input v-model="editForm.algVersion" /></el-form-item>
    <el-form-item label="权重路径"><el-input v-model="editForm.algWeightPath" disabled /></el-form-item>
    <el-form-item label="启用状态"><el-switch v-model="editForm.algEnabled" /></el-form-item>
    <el-form-item label="默认配置"><el-input v-model="editForm.algDefaultConfText" type="textarea" :rows="6" /></el-form-item>
  </el-form>
  <template #footer>
    <el-button @click="editDialogVisible = false">取消</el-button>
    <el-button type="primary" @click="saveEdit">保存</el-button>
  </template>
</el-dialog>
```

- [ ] **Step 5: Add upload dialog**

Add before the existing bind dialog:

```vue
<el-dialog v-model="uploadDialogVisible" title="上传算法权重版本" width="620px" destroy-on-close>
  <el-form :model="uploadForm" label-width="110px">
    <el-form-item label="算法名称"><el-input v-model="uploadForm.algName" /></el-form-item>
    <el-form-item label="算法编号"><el-input v-model="uploadForm.algSerial" /></el-form-item>
    <el-form-item label="算法版本"><el-input v-model="uploadForm.algVersion" /></el-form-item>
    <el-form-item label="默认配置"><el-input v-model="uploadForm.algDefaultConf" type="textarea" :rows="5" /></el-form-item>
    <el-form-item label="权重文件">
      <el-upload ref="uploadRef" :auto-upload="false" :limit="1" :on-change="handleWeightSelected" :on-remove="handleWeightRemoved">
        <el-button type="primary">选择文件</el-button>
      </el-upload>
    </el-form-item>
    <el-progress v-if="uploadProgress > 0" :percentage="uploadProgress" />
  </el-form>
  <template #footer>
    <el-button @click="uploadDialogVisible = false">取消</el-button>
    <el-button type="primary" :loading="uploading" @click="submitWeightUpload">上传并创建版本</el-button>
  </template>
</el-dialog>
```

- [ ] **Step 6: Add script state**

Add after existing refs:

```javascript
const editDialogVisible = ref(false)
const uploadDialogVisible = ref(false)
const uploadRef = ref()
const uploadFile = ref(null)
const uploading = ref(false)
const uploadProgress = ref(0)
const editForm = reactive({
  algId: undefined,
  algName: '',
  algSerial: '',
  algVersion: '',
  algWeightPath: '',
  algEnabled: true,
  algDefaultConfText: '{}'
})
const uploadForm = reactive({
  algName: '',
  algSerial: '',
  algVersion: '',
  algDefaultConf: '{}'
})
```

- [ ] **Step 7: Add edit and upload methods**

Add:

```javascript
function openEditDialog(row) {
  Object.assign(editForm, {
    algId: row?.algId,
    algName: row?.algName || '',
    algSerial: row?.algSerial || '',
    algVersion: row?.algVersion || '',
    algWeightPath: row?.algWeightPath || '',
    algEnabled: row?.algEnabled !== false,
    algDefaultConfText: JSON.stringify(parseJson(row?.algDefaultConf), null, 2)
  })
  editDialogVisible.value = true
}

async function saveEdit() {
  let algDefaultConf
  try {
    algDefaultConf = JSON.stringify(JSON.parse(editForm.algDefaultConfText || '{}'))
  } catch {
    proxy.$modal.msgError('默认配置必须是合法 JSON')
    return
  }
  const payload = {
    algId: editForm.algId,
    algName: editForm.algName,
    algSerial: editForm.algSerial,
    algVersion: editForm.algVersion,
    algWeightPath: editForm.algWeightPath,
    algEnabled: editForm.algEnabled,
    algDefaultConf
  }
  if (payload.algId) {
    await updateAlgorithm(payload)
  } else {
    await addAlgorithm(payload)
  }
  proxy.$modal.msgSuccess('保存成功')
  editDialogVisible.value = false
  getList()
}

function openUploadDialog() {
  Object.assign(uploadForm, { algName: '', algSerial: '', algVersion: '', algDefaultConf: '{}' })
  uploadFile.value = null
  uploadProgress.value = 0
  uploadDialogVisible.value = true
}

function handleWeightSelected(file) {
  uploadFile.value = file.raw
}

function handleWeightRemoved() {
  uploadFile.value = null
}

async function submitWeightUpload() {
  if (!uploadFile.value) {
    proxy.$modal.msgError('请选择权重文件')
    return
  }
  uploading.value = true
  uploadProgress.value = 0
  const formData = new FormData()
  formData.append('alg_name', uploadForm.algName)
  formData.append('alg_serial', uploadForm.algSerial)
  formData.append('alg_version', uploadForm.algVersion)
  formData.append('alg_default_conf', uploadForm.algDefaultConf || '{}')
  formData.append('file', uploadFile.value)
  try {
    await uploadAlgorithmWeight(formData, event => {
      if (event.total) uploadProgress.value = Math.round((event.loaded * 100) / event.total)
    })
    proxy.$modal.msgSuccess('上传成功')
    uploadDialogVisible.value = false
    getList()
  } finally {
    uploading.value = false
  }
}
```

- [ ] **Step 8: Add edit buttons to operations**

In the operation column, add:

```vue
<el-button link type="primary" icon="Edit" @click="openEditDialog(scope.row)">编辑</el-button>
```

Keep existing detail, bind, delete buttons.

---

### Task 8: Make Camera Binding Version-Aware

**Files:**
- Modify: `ruoyi-fastapi-frontend/src/views/algorithm/list/index.vue`
- Backend behavior supported by: `ruoyi-fastapi-backend/algorithm/runtime_service.py`

- [ ] **Step 1: Include weight path and enabled in normalized algorithm item**

Replace `normalizeAlgorithmItem` body with:

```javascript
  return {
    algId: item.algId,
    algName: item.algName || '',
    algVersion: item.algVersion || '',
    algSerial: item.algSerial || '',
    algWeightPath: item.algWeightPath || '',
    algEnabled: item.algEnabled !== false,
    algDefaultConf: parseJson(item.algDefaultConf),
  }
```

- [ ] **Step 2: Make display names include version**

Add:

```javascript
function algorithmDisplayName(algorithm) {
  const version = algorithm.algVersion ? `(${algorithm.algVersion})` : ''
  return `${algorithm.algName || algorithm.algSerial || '未命名算法'}${version}`
}
```

- [ ] **Step 3: Update saveBinding names**

Replace:

```javascript
      video.vidAlgorithmName = algorithmList.map(item => item.algName || targetAlgName)
```

with:

```javascript
      video.vidAlgorithmName = algorithmList.map(item => algorithmDisplayName(item))
```

- [ ] **Step 4: Prevent binding disabled algorithms**

At the start of `showBindDialog(row)`, add:

```javascript
  if (row.algEnabled === false) {
    proxy.$modal.msgWarning('该算法版本已停用，不能绑定摄像头')
    return
  }
```

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd ruoyi-fastapi-frontend
npm run build:stage
```

Expected: build exits 0.

---

### Task 9: Verify Backend and Runtime Together

**Files:**
- Verify: backend changed files

- [ ] **Step 1: Run backend compile verification**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python -m compileall algorithm/runtime_service.py module_xuzhou/entity/do/alg_do.py module_xuzhou/entity/vo/alg_vo.py module_xuzhou/dao/alg_dao.py module_xuzhou/service/alg_service.py module_xuzhou/controller/algorithm_controller.py tests/test_multi_camera_analysis.py tests/test_algorithm_management.py
```

Expected: command exits 0.

- [ ] **Step 2: Run backend tests**

Run:

```bash
cd ruoyi-fastapi-backend
PYTHONPATH=. uv run python tests/test_multi_camera_analysis.py
PYTHONPATH=. uv run python tests/test_algorithm_management.py
```

Expected: both commands exit 0.

- [ ] **Step 3: Manually verify upload folder behavior locally**

Start backend if needed:

```bash
cd ruoyi-fastapi-backend
uv run app.py --env=dev
```

Use the frontend upload page or an API client to upload a small `.onnx` test file. Expected result:
- File exists under `ruoyi-fastapi-backend/algorithm/weights/{algSerial}/{algVersion}/`.
- `/xuzhou/algorithm/list` shows the new row with `algWeightPath` and `algEnabled`.

---

### Task 10: Browser Verify Frontend Flow

**Files:**
- Verify: `ruoyi-fastapi-frontend/src/views/algorithm/list/index.vue`

- [ ] **Step 1: Start frontend dev server**

Run:

```bash
cd ruoyi-fastapi-frontend
npm run dev
```

Expected: Vite dev server starts on configured port.

- [ ] **Step 2: Open algorithm management page**

In the browser, navigate to the algorithm list page. Expected:
- Algorithm rows display name, code, version, weight path, enabled status, config preview.
- Upload button and add button are visible.

- [ ] **Step 3: Upload a weight version**

Use a small model file with extension `.onnx`, `.pt`, `.pth`, `.bin`, or `.engine`. Expected:
- Progress bar advances.
- Success message appears.
- New algorithm version row appears in the table.

- [ ] **Step 4: Bind the uploaded version to a camera**

Click `绑定摄像头` on the new version and move one camera to the bound side. Expected:
- Save succeeds.
- Reopening the dialog shows the camera still bound.
- Camera bound names include the algorithm version, for example `烟火检测(v1)`.

- [ ] **Step 5: Verify disabled version cannot bind**

Edit the algorithm and disable it. Try binding again. Expected:
- Frontend shows `该算法版本已停用，不能绑定摄像头`.
- No camera binding changes are made.

---

## Self-Review

Spec coverage:
- Database-managed algorithms: Tasks 1, 3, 4.
- No scene field: no task adds one.
- Multiple weight versions: Tasks 1, 4, 7.
- Weight files under `algorithm/weights`: Tasks 4, 9, 10.
- New upload creates new version: Task 4 duplicate guard and upload behavior.
- Camera binds specific versions: Tasks 2, 8, 10.
- Runtime receives version/weight/config: Task 2.
- Frontend management and upload: Tasks 6, 7, 10.

Placeholder scan: no implementation step contains unresolved placeholders.

Type consistency:
- Backend Python uses snake_case fields: `alg_weight_path`, `alg_enabled`.
- API/frontend aliases use camelCase fields: `algWeightPath`, `algEnabled`.
- Camera binding JSON stores camelCase fields because existing frontend and runtime already consume `vidAlgorithm` in camelCase.
