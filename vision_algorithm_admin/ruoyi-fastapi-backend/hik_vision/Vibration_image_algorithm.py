import cv2
import numpy as np
import os

from scipy import ndimage, signal


class VibraimageCore:
    """固定输入图像分辨率为640x480"""

    def __init__(self):
        self.FIXED_WIDTH = 640
        self.FIXED_HEIGHT = 480
        self.FIXED_RESOLUTION = (self.FIXED_WIDTH, self.FIXED_HEIGHT)
        # 计算参数
        self.halo_params = {
            "FACE_DILATE_RATIO": 1.3,
            "NOISE_THRESHOLD": 0.001,
            "ACCUMULATE_FRAMES": 50,  # 用来计算振幅的累积帧数
        }
        # 处理参数
        self.time_window = 20  # 频谱分析窗口
        self.fps = 30  # 默认帧率
        # 数据容器
        self.vibration_energies = []
        self.left_amplitudes = []
        self.right_amplitudes = []
        self.left_max_freqs = []
        self.right_max_freqs = []
        self.frequency_data = []
        self.power_spectrum = []
        self.frame_buffer = []
        self.A = None  # 振幅矩阵
        self.F = None  # 频率矩阵
        self.A_norm = None
        self.F_norm = None
        # 人脸区域
        self.face_rect = None  # (x,y,w,h)框
        self.left_face_rect = None
        self.right_face_rect = None
        # 参数历史
        self.e_history = {f"e{i}": [] for i in range(1, 11)}

    def _detect_face(self, frame_640):
        """优先使用DNN"""
        model_file = "res10_300x300_ssd_iter_140000.caffemodel"
        config_file = "deploy. prototxt"
        if os.path.exists(model_file) and os.path.exists(config_file):
            net = cv2.dnn.readNetFromCaffe(config_file, model_file)
            h, w = frame_640.shape[: 2]
            blob = cv2.dnn.blobFromImage(frame_640, 1.0, (300, 300), (104.0, 177.0, 123.0))
            net.setInput(blob)
            detections = net.forward()
            for i in range(detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                if confidence > 0.5:
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (x, y, x1, y1) = box.astype("int")
                    return (x, y, x1 - x, y1 - y)
        # 备用Haar
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            classifier = cv2.CascadeClassifier(cascade_path)
            gray = cv2.cvtColor(frame_640, cv2.COLOR_BGR2GRAY)
            faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
            if len(faces) > 0:
                return max(faces, key=lambda r: r[2] * r[3])
        return None

    def _preprocess_head_region(self, frame_640, face_rect):
        """提取并缩放到180x180的灰度人脸区域"""
        x, y, w, h = face_rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, self.FIXED_WIDTH - x)
        h = min(h, self.FIXED_HEIGHT - y)
        gray = cv2.cvtColor(frame_640, cv2.COLOR_BGR2GRAY)
        head_roi = gray[y:y + h, x:x + w]
        head_resized = cv2.resize(head_roi, (180, 180), interpolation=cv2.INTER_LINEAR)
        return head_resized / 255.0, (x, y, w, h)

    def _calculate_vibra_params(self, frame_buffer):
        """计算振幅A和频率F矩阵"""
        if len(frame_buffer) < 2:
            return np.zeros((180, 180)), np.zeros((180, 180))
        A = np.zeros_like(frame_buffer[0], dtype=np.float32)
        F = np.zeros_like(frame_buffer[0], dtype=np.float32)
        for i in range(len(frame_buffer) - 1):
            diff = np.abs(frame_buffer[i] - frame_buffer[i + 1])
            diff[diff < self.halo_params['NOISE_THRESHOLD']] = 0
            A += diff
            F[diff > 0] += 1
        frame_count = len(frame_buffer)
        A = A / frame_count
        F = (F / frame_count) * self.fps
        A = ndimage.gaussian_filter(A, sigma=1.5)
        F = ndimage.gaussian_filter(F, sigma=1.5)
        return A, F

    def _normalize_vibra_params(self):
        """归一化振幅和频率"""
        if self.A is not None and self.A.size > 0:
            a_min, a_max = np.percentile(self.A, 5), np.percentile(self.A, 95)
            if a_max - a_min > 1e-8:
                self.A_norm = np.clip((self.A - a_min) / (a_max - a_min), 0, 1)
            else:
                self.A_norm = np.zeros_like(self.A)
        if self.F is not None and self.F.size > 0:
            f_min, f_max = np.percentile(self.F, 5), np.percentile(self.F, 95)
            if f_max - f_min > 1e-8:
                self.F_norm = np.clip((self.F - f_min) / (f_max - f_min), 0, 1)
            else:
                self.F_norm = np.zeros_like(self.F)

    def _calculate_all_parameters(self):
        """计算e1到e10的所有参数（与1117.py逻辑一致）"""

        # ======================== e1: 攻击性 ========================
        if self.vibration_energies:
            mean_energy = np.mean(self.vibration_energies)
            std_energy = np.std(self.vibration_energies)
            max_energy = np.max(self.vibration_energies) if self.vibration_energies else 1
            e1 = (mean_energy + std_energy) / max_energy * 100 if max_energy != 0 else 0
        else:
            e1 = 0
        self.e_history['e1'].append(e1)

        # ======================== e2: 压力 ========================
        n = len(self.left_amplitudes)
        if n > 0:
            sum_val = 0
            for i in range(n):
                A_L = self.left_amplitudes[i]
                A_R = self.right_amplitudes[i]
                A_max = max(A_L, A_R) if (A_L != 0 or A_R != 0) else 1
                F_L = self.left_max_freqs[i]
                F_R = self.right_max_freqs[i]
                F_max = max(F_L, F_R) if (F_L != 0 or F_R != 0) else 1
                term1 = abs(A_L - A_R) / A_max if A_max != 0 else 0
                term2 = abs(F_L - F_R) / F_max if F_max != 0 else 0
                sum_val += term1 + term2
            e2 = (sum_val / (2 * n)) * 100 if n > 0 else 0
        else:
            e2 = 0
        self.e_history['e2'].append(e2)

        # ======================== e3: 焦虑 ========================
        e3 = 0
        valid_psd = []
        valid_freq = []
        if len(self.power_spectrum) > 0 and len(self.frequency_data) > 0:
            lengths = [len(psd) for psd in self.power_spectrum]
            if lengths:
                most_common_length = max(set(lengths), key=lengths.count)
                for psd, freq in zip(self.power_spectrum, self.frequency_data):
                    if len(psd) == most_common_length and len(freq) == most_common_length:
                        valid_psd.append(psd)
                        valid_freq.append(freq)
            if len(valid_psd) > 0 and len(valid_freq) > 0:
                avg_psd = np.mean(valid_psd, axis=0)
                avg_freq = np.mean(valid_freq, axis=0)
                f_max = np.max(avg_freq) if avg_freq.size > 0 else 1
                high_freq_mask = (avg_freq >= f_max / 2) & (avg_freq <= f_max)
                total_mask = avg_freq <= f_max
                high_freq_power = np.sum(avg_psd[high_freq_mask]) if high_freq_mask.size > 0 else 0
                total_power = np.sum(avg_psd[total_mask]) if total_mask.size > 0 else 1
                e3 = (high_freq_power / total_power * 100) if total_power > 0 else 0
        e3 = max(0, min(100, e3))
        self.e_history['e3'].append(e3)

        # ======================== e4: 可疑 ========================
        e4 = (e1 + e2 + e3) / 3
        self.e_history['e4'].append(e4)

        # ======================== e5: 平衡 ========================
        e5 = 100
        if len(self.vibration_energies) > 1:
            mean_energy = np.mean(self.vibration_energies)
            if mean_energy != 0:
                std_energy = np.std(self.vibration_energies)
                Va = std_energy / mean_energy
                e5 = max(0, min(100, (100 - 2 * Va)))
        self.e_history['e5'].append(e5)

        # ======================== e6: 魅力 ========================
        e6 = 0
        if len(self.left_amplitudes) > 0 and len(self.right_amplitudes) > 0:
            min_len = min(len(self.left_amplitudes), len(self.right_amplitudes),
                          len(self.left_max_freqs), len(self.right_max_freqs))
            if min_len > 0:
                left_amps = self.left_amplitudes[:min_len]
                right_amps = self.right_amplitudes[:min_len]
                left_freqs = self.left_max_freqs[:min_len]
                right_freqs = self.right_max_freqs[:min_len]

                line_params = []
                for la, ra, lf, rf in zip(left_amps, right_amps, left_freqs, right_freqs):
                    W_dif = abs(la - ra)
                    max_W = max(max(left_amps), max(right_amps)) if (max(left_amps) > 0 or max(right_amps) > 0) else 1
                    C_dif = abs(lf - rf)
                    line_params.append((W_dif / max_W) + (C_dif / 255))

                e6 = max(0, min(100, (sum(line_params) / len(line_params)) * 100)) if line_params else 0
        self.e_history['e6'].append(e6)

        # ======================== e7: 能量 ========================
        e7 = 0
        if len(self.frequency_data) > 0:
            all_freqs = []
            for freq_arr in self.frequency_data:
                all_freqs.extend(freq_arr)
            if all_freqs:
                F_pz = max(all_freqs)
                freq_counts = {}
                for freq in all_freqs:
                    freq_int = int(freq)
                    freq_counts[freq_int] = freq_counts.get(freq_int, 0) + 1
                M = max(freq_counts.values()) if freq_counts else 0
                sigma = np.std(all_freqs) if all_freqs else 0
                e7 = max(0, min(100, ((M - sigma) / F_pz) * 100)) if F_pz != 0 else 0
        self.e_history['e7'].append(e7)

        # ======================== e8: 自我调节 ========================
        e8 = 0
        if len(self.e_history['e5']) >= 2 and len(self.e_history['e6']) >= 2:
            dE5 = np.max(self.e_history['e5']) - np.min(self.e_history['e5'])
            EE5 = np.mean(self.e_history['e5'])
            dE6 = np.max(self.e_history['e6']) - np.min(self.e_history['e6'])
            EE6 = np.mean(self.e_history['e6'])
            denominator = dE5 + dE6 + EE5 + EE6
            e8 = max(0, min(100, (1 - (dE5 + dE6) / denominator) * 100)) if denominator != 0 else 100
        self.e_history['e8'].append(e8)

        # ======================== e9: 抑制 ========================
        e9 = (e1 + e5) / 2
        self.e_history['e9'].append(e9)

        # ======================== e10: 神经质 ========================
        e10 = (e2 + e3) / 2
        self.e_history['e10'].append(e10)

        results = {
            'e1': round(e1, 2),
            'e2': round(e2, 2),
            'e3': round(e3, 2),
            'e4': round(e4, 2),
            'e5': round(e5, 2),
            'e6': round(e6, 2),
            'e7': round(e7, 2),
            'e8': round(e8, 2),
            'e9': round(e9, 2),
            'e10': round(e10, 2)
        }
        return results

    def process_video(self, video_path, manual_face_rect=None):
        """处理视频文件"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("无法打开视频文件")
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_idx = 0
        first_frame = True
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_640 = cv2.resize(frame, self.FIXED_RESOLUTION)
            # 第一帧检测人脸
            if first_frame:
                if manual_face_rect is not None:
                    self.face_rect = np.array([manual_face_rect])
                else:
                    detected = self._detect_face(frame_640)
                    if detected is None:
                        cap.release()
                        raise RuntimeError("未检测到人脸,请提供manual_face_rect参数")
                    self.face_rect = np.array([detected])
                x, y, w, h = self.face_rect[0]
                center_x = x + w // 2
                self.left_face_rect = (x, y, w // 2, h)
                self.right_face_rect = (center_x, y, w - w // 2, h)
                first_frame = False
            # 使用第一帧检测到的人脸区域
            x, y, w, h = self.face_rect[0]
            lx, ly, lw, lh = self.left_face_rect
            rx, ry, rw, rh = self.right_face_rect
            # 预处理人脸区域
            preprocessed, _ = self._preprocess_head_region(frame_640, (x, y, w, h))
            self.frame_buffer.append(preprocessed)
            if len(self.frame_buffer) > self.halo_params['ACCUMULATE_FRAMES']:
                self.frame_buffer.pop(0)
            # 足够帧之后开始计算振动参数
            if len(self.frame_buffer) == self.halo_params['ACCUMULATE_FRAMES']:
                self.A, self.F = self._calculate_vibra_params(self.frame_buffer)
                self._normalize_vibra_params()
                left_roi = frame_640[ly:ly + lh, lx:lx + lw]
                right_roi = frame_640[ry:ry + rh, rx:rx + rw]
                left_gray = cv2.cvtColor(left_roi, cv2.COLOR_BGR2GRAY) / 255.0
                right_gray = cv2.cvtColor(right_roi, cv2.COLOR_BGR2GRAY) / 255.0
                left_ampl = np.sum(np.abs(left_gray - np.mean(left_gray)))
                right_ampl = np.sum(np.abs(right_gray - np.mean(right_gray)))
                left_freq = np.max(left_gray) if np.max(left_gray) > 0 else 0.001
                right_freq = np.max(right_gray) if np.max(right_gray) > 0 else 0.001
                energy = np.sum(self.A ** 2) if self.A.size > 0 else 0
                self.vibration_energies.append(energy)
                self.left_amplitudes.append(left_ampl)
                self.right_amplitudes.append(right_ampl)
                self.left_max_freqs.append(left_freq)
                self.right_max_freqs.append(right_freq)
                # 频谱分析
                if frame_idx % self.time_window == 0 and len(self.vibration_energies) >= self.time_window:
                    energy_arr = np.array(self.vibration_energies[-self.time_window:])
                    freqs, psd = signal.welch(energy_arr, self.fps, nperseg=min(self.time_window, 1024))
                    self.frequency_data.append(freqs)
                    self.power_spectrum.append(psd)
            frame_idx += 1
        cap.release()
        # 计算10个参数
        results = self._calculate_all_parameters()
        return results
