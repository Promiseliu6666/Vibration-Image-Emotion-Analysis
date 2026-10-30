# 本地手机实物检测
使用 ONNX Model Zoo SSD-MobileNetV1 opset12，COCO 稀疏类别编号77为cell phone。
来源：https://github.com/onnx/models/tree/main/validated/vision/object_detection_segmentation/ssd-mobilenetv1
模型下载：https://media.githubusercontent.com/media/onnx/models/main/validated/vision/object_detection_segmentation/ssd-mobilenetv1/model/ssd_mobilenet_v1_12.onnx
使用已有 ONNX Runtime 在本机推理，不上传图片。模型及许可遵循来源仓库；项目原行为模型保留。
手机置信度至少0.55，手部可见性至少0.65，连续3次且至少2秒证据才确认。
手机遮挡、背光、小尺寸会漏检；手机放在桌上且没有可见手部交互不记为使用。

2026-10-12 更新：全画面手机阈值仍为 0.55；全画面未关联到手持手机时，对最多两个可见手部区域补充局部检测，局部阈值 0.40，框映射回原图后仍要求可见手部关联与连续三次证据。确认窗口 12 秒、断帧超过 6 秒重置，不延续旧手机状态；重复时间戳不计入确认。用户提供的漏检截图已通过回归，但静态截图复测不等于全场景准确率评估。

2026-10-13 更新：手部局部检测使用原始摄像头分辨率，不复用缩小后的姿态分析图；同一手机的重叠框合并，非法坐标过滤。背景姿态不触发局部扫描，单个局部模型异常保留其他证据。已归档手机原图回归仍可确认；未完成全场景准确率评估。
