"""振动图像心理状态分析：基于帧间像素差分的14项心理参数计算

从滨化项目 VibraimageCore 适配而来，适配小智watcher的低帧率拍照上传模式。

核心改动：
1. 移除 DNN/Haar 人脸检测 — 人脸区域由外部 (MediaPipe) 传入
2. ACCUMULATE_FRAMES 从50降至10，适配0.5~2 FPS的拍照模式
3. FPS 从外部传入实际帧率，而非固定30
4. 新增 get_results() — 无新帧时也能获取最近一次计算结果
"""

import numpy as np
import cv2
from collections import deque
from scipy import signal
import scipy.stats as stats


class VibraimageCore:
    """固定输入图像分辨率为640x480，人脸区域缩放到180x180"""

    def __init__(self):
        self.FIXED_WIDTH = 640
        self.FIXED_HEIGHT = 480

        # 计算参数 — 降低积攒帧数以适配低帧率拍照模式
        self.accumulate_frames = 10   # 50→10，约5-20秒出一次结果
        self.fps = 1.0                # 默认1FPS，由外部传入实际帧率
        self.noise_threshold = 0.001  # 像素差分噪声阈值
        self.time_window = 10         # 频谱分析窗口

        # 数据容器
        self.vibration_energies: deque = deque(maxlen=100)
        self.left_amplitudes: deque = deque(maxlen=100)
        self.right_amplitudes: deque = deque(maxlen=100)
        self.left_max_freqs: deque = deque(maxlen=100)
        self.right_max_freqs: deque = deque(maxlen=100)
        self.frequency_data: deque = deque(maxlen=100)
        self.power_spectrum: deque = deque(maxlen=100)

        self.frame_buffer: deque = deque(maxlen=self.accumulate_frames)
        self.A = None   # 振幅矩阵 (180x180)
        self.F = None   # 频率矩阵 (180x180)
        self.A_norm = None
        self.F_norm = None

        # 人脸区域 — 由外部传入，不再内部检测
        self.face_rect = None        # (x, y, w, h)
        self.left_face_rect = None   # (x, y, w, h)
        self.right_face_rect = None  # (x, y, w, h)

        # 14个参数的历史（用于计算波动性等依赖历史的参数）
        self.e1_history: deque = deque(maxlen=50)
        self.e2_history: deque = deque(maxlen=50)
        self.e3_history: deque = deque(maxlen=50)
        self.e4_history: deque = deque(maxlen=50)
        self.e5_history: deque = deque(maxlen=50)
        self.e6_history: deque = deque(maxlen=50)
        self.e7_history: deque = deque(maxlen=50)
        self.e8_history: deque = deque(maxlen=50)
        self.e9_history: deque = deque(maxlen=50)
        self.e10_history: deque = deque(maxlen=50)
        self.e11_history: deque = deque(maxlen=50)
        self.e12_history: deque = deque(maxlen=50)
        self.e13_history: deque = deque(maxlen=50)
        self.e14_history: deque = deque(maxlen=50)

        # 最近一次完整计算结果
        self.latest_results: dict | None = None

        self.frame_idx = 0
        self.face_initialized = False

    def reset(self):
        """重置所有状态以支持新分析会话"""
        self.vibration_energies.clear()
        self.left_amplitudes.clear()
        self.right_amplitudes.clear()
        self.left_max_freqs.clear()
        self.right_max_freqs.clear()
        self.frequency_data.clear()
        self.power_spectrum.clear()
        self.frame_buffer.clear()
        self.A = None
        self.F = None
        self.A_norm = None
        self.F_norm = None
        self.face_rect = None
        self.left_face_rect = None
        self.right_face_rect = None
        for attr in [f"e{i}_history" for i in range(1, 15)]:
            getattr(self, attr).clear()
        self.latest_results = None
        self.frame_idx = 0
        self.face_initialized = False

    def set_face_rect(self, x: int, y: int, w: int, h: int):
        """由外部（MediaPipe）设置人脸区域"""
        if w <= 0 or h <= 0:
            return
        self.face_rect = (int(x), int(y), int(w), int(h))
        center_x = x + w // 2
        self.left_face_rect = (x, y, w // 2, h)
        self.right_face_rect = (center_x, y, w - w // 2, h)
        self.face_initialized = True

    def _preprocess_head_region(self, frame):
        """提取并缩放到180x180的灰度人脸区域"""
        x, y, w, h = self.face_rect
        x = max(0, x)
        y = max(0, y)
        w = min(w, frame.shape[1] - x)
        h = min(h, frame.shape[0] - y)
        if w <= 0 or h <= 0:
            return None
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        head_roi = gray[y:y + h, x:x + w]
        head_resized = cv2.resize(head_roi, (180, 180), interpolation=cv2.INTER_LINEAR)
        return head_resized / 255.0

    def _calculate_vibra_params(self):
        """计算振幅A和频率F矩阵"""
        if len(self.frame_buffer) < 2:
            return np.zeros((180, 180)), np.zeros((180, 180))

        buf = list(self.frame_buffer)
        A = np.zeros_like(buf[0], dtype=np.float32)
        F = np.zeros_like(buf[0], dtype=np.float32)

        for i in range(len(buf) - 1):
            diff = np.abs(buf[i] - buf[i + 1])
            diff[diff < self.noise_threshold] = 0
            A += diff
            F[diff > 0] += 1

        frame_count = len(buf)
        A = A / frame_count
        F = (F / frame_count) * self.fps
        return A, F

    def _normalize_vibra_params(self):
        """归一化振幅和频率矩阵"""
        if self.A is not None:
            a_min, a_max = self.A.min(), self.A.max()
            self.A_norm = (self.A - a_min) / (a_max - a_min + 1e-6) if a_max > a_min else np.zeros_like(self.A)
        if self.F is not None:
            f_min, f_max = self.F.min(), self.F.max()
            self.F_norm = (self.F - f_min) / (f_max - f_min + 1e-6) if f_max > f_min else np.zeros_like(self.F)

    # ================================================================
    #  14 项参数计算（核心算法，与滨化项目完全一致）
    # ================================================================

    def _calculate_all_parameters(self) -> dict:
        """计算所有14个参数 e1-e14

        高频模式（FPS ≥ 3）：使用原始频谱分析方法
        低频模式（FPS < 3）：使用时域替代方法，避免 bincount/Welch 在低采样率下失效
        """
        results = {}
        use_time_domain = self.fps < 3.0  # 低于3FPS用替代算法

        # ---- e1: Aggression（攻击性）----
        if self.vibration_energies:
            energies = np.array(self.vibration_energies)
            mean_e = np.mean(energies)
            std_e = np.std(energies)
            max_e = np.max(energies) if len(energies) > 0 else 1
            e1 = (mean_e + std_e) / max_e * 100 if max_e != 0 else 0
        else:
            e1 = 0
        results["e1"] = round(max(0, min(100, e1)), 2)
        self.e1_history.append(results["e1"])

        # ---- e2: Stress（压力）----
        e2 = 0
        if self.left_amplitudes and self.right_amplitudes and self.left_max_freqs and self.right_max_freqs:
            n = min(len(self.left_amplitudes), len(self.right_amplitudes),
                    len(self.left_max_freqs), len(self.right_max_freqs))
            if n > 0:
                sum_val = 0
                for i in range(n):
                    A_L = self.left_amplitudes[i]
                    A_R = self.right_amplitudes[i]
                    F_L = self.left_max_freqs[i]
                    F_R = self.right_max_freqs[i]
                    A_max = max(A_L, A_R, 1)
                    F_max = max(F_L, F_R, 1)
                    sum_val += (abs(A_L - A_R) / A_max + abs(F_L - F_R) / F_max)
                e2 = (sum_val / (2 * n)) * 100
        results["e2"] = round(max(0, min(100, e2)), 2)
        self.e2_history.append(results["e2"])

        # ---- e3: Tension（紧张）----
        # 高频：频谱高频功率占比   低频：振动能量抖动率
        if use_time_domain:
            e3 = self._calc_tension_time_domain()
        else:
            e3 = self._calc_tension_spectral()
        results["e3"] = round(max(0, min(100, e3)), 2)
        self.e3_history.append(results["e3"])

        # ---- e4: Suspiciousness（疑虑）----
        e4 = (results["e1"] + results["e2"] + results["e3"]) / 3
        results["e4"] = round(e4, 2)
        self.e4_history.append(results["e4"])

        # ---- e5: Balance（平衡）----
        e5 = 100
        if self.vibration_energies:
            energies = np.array(self.vibration_energies)
            mean_e = np.mean(energies)
            if mean_e > 0:
                Va = np.std(energies) / mean_e
                e5 = max(0, min(100, 100 - 2 * Va * 100))
        results["e5"] = round(e5, 2)
        self.e5_history.append(results["e5"])

        # ---- e6: Charm（魅力）----
        e6 = 0
        if self.left_amplitudes and self.right_amplitudes and self.left_max_freqs and self.right_max_freqs:
            n = min(len(self.left_amplitudes), len(self.right_amplitudes))
            if n > 0:
                sum_diff = 0
                for i in range(n):
                    A_diff = abs(self.left_amplitudes[i] - self.right_amplitudes[i])
                    F_diff = abs(self.left_max_freqs[i] - self.right_max_freqs[i])
                    sum_diff += A_diff + F_diff / 255
                e6 = (sum_diff / n) * 100
                e6 = 100 - e6  # 高对称 = 高魅力
        results["e6"] = round(max(0, min(100, e6)), 2)
        self.e6_history.append(results["e6"])

        # ---- e7: Energy（活力）----
        # 高频：频率分布集中度   低频：振幅强度 × 规律性
        if use_time_domain:
            e7 = self._calc_energy_time_domain()
        else:
            e7 = self._calc_energy_spectral()
        results["e7"] = round(max(0, min(100, e7)), 2)
        self.e7_history.append(results["e7"])

        # ---- e8: Self-regulation（自控力）----
        e8 = 100
        if len(self.e5_history) >= 2 and len(self.e6_history) >= 2:
            dE5 = np.max(self.e5_history) - np.min(self.e5_history)
            dE6 = np.max(self.e6_history) - np.min(self.e6_history)
            E5 = np.mean(self.e5_history)
            E6 = np.mean(self.e6_history)
            denom = dE5 + dE6 + E5 + E6
            e8 = (1 - (dE5 + dE6) / denom) * 100 if denom > 0 else 100
        results["e8"] = round(max(0, min(100, e8)), 2)
        self.e8_history.append(results["e8"])

        # ---- e9: Inhibition（抑制力）----
        e9 = (results["e1"] + results["e5"]) / 2
        results["e9"] = round(e9, 2)
        self.e9_history.append(results["e9"])

        # ---- e10: Neuroticism（神经质）----
        e10 = (results["e2"] + results["e3"]) / 2
        results["e10"] = round(e10, 2)
        self.e10_history.append(results["e10"])

        # ---- e11: Gloominess（忧郁）----
        # 高频：频率均值偏离0.5   低频：振动能量下降趋势
        if use_time_domain:
            e11 = self._calc_gloominess_time_domain()
        else:
            e11 = self._calc_gloominess_spectral()
        results["e11"] = round(max(0, min(100, e11)), 2)
        self.e11_history.append(results["e11"])

        # ---- e12: Happiness（幸福指数）----
        e12 = 0
        if len(self.e8_history) > 0 and len(self.e7_history) > 0:
            I = np.mean(self.e8_history)
            E = np.mean(self.e7_history)
            dI = np.std(self.e8_history) if len(self.e8_history) > 1 else 0
            dE = np.std(self.e7_history) if len(self.e7_history) > 1 else 0
            denom = I + E + dI + dE
            e12 = (I / denom * 100) if denom > 0 else 0
        results["e12"] = round(max(0, min(100, e12)), 2)
        self.e12_history.append(results["e12"])

        # ---- e13: Extraversion（外向性）----
        e13 = 50  # 默认值（中等外向）
        if len(self.e8_history) >= 2 and len(self.e7_history) >= 2:
            e8_arr = np.array(self.e8_history)
            e7_arr = np.array(self.e7_history)
            std_e8 = np.std(e8_arr)
            std_e7 = np.std(e7_arr)
            if std_e8 == 0 or std_e7 == 0:
                r = 1.0 if (std_e8 == 0 and std_e7 == 0) else 0.0
            else:
                try:
                    r, _ = stats.pearsonr(e8_arr, e7_arr)
                except Exception:
                    r = 0.0
            e13 = (r + 1) / 2 * 100
        results["e13"] = round(max(0, min(100, e13)), 2)
        self.e13_history.append(results["e13"])

        # ---- e14: Stability（稳定性）----
        # 高频：频率分布正态拟合   低频：长期能量稳定性
        if use_time_domain:
            e14 = self._calc_stability_time_domain()
        else:
            e14 = self._calc_stability_spectral()
        results["e14"] = round(max(0, min(100, e14)), 2)
        self.e14_history.append(results["e14"])

        return results

    # ================================================================
    #  原始频谱方法（FPS ≥ 3 时使用）
    # ================================================================

    def _calc_tension_spectral(self) -> float:
        """e3: 高频振动功率占比 → 紧张度"""
        if not self.power_spectrum or not self.frequency_data:
            return 0.0
        lengths = [len(p) for p in self.power_spectrum]
        if not lengths:
            return 0.0
        most_common_len = max(set(lengths), key=lengths.count)
        valid_psd = [p for p, f in zip(self.power_spectrum, self.frequency_data) if len(p) == most_common_len]
        valid_freq = [f for f in self.frequency_data if len(f) == most_common_len]
        if not valid_psd:
            return 0.0
        avg_psd = np.mean(valid_psd, axis=0)
        avg_freq = np.mean(valid_freq, axis=0)
        f_max = np.max(avg_freq) if avg_freq.size > 0 else 1
        high_power = np.sum(avg_psd[avg_freq >= f_max / 2])
        total_power = np.sum(avg_psd[avg_freq >= 0.1])
        return (high_power / total_power * 100) if total_power > 0 else 0.0

    def _calc_energy_spectral(self) -> float:
        """e7: 频率分布集中度 → 活力"""
        if not self.frequency_data:
            return 0.0
        all_freqs = np.concatenate(list(self.frequency_data)) if self.frequency_data else np.array([])
        if len(all_freqs) == 0:
            return 0.0
        F_ps = np.max(all_freqs)
        freq_counts = np.bincount(np.round(all_freqs).astype(int))
        M = np.max(freq_counts) if len(freq_counts) > 0 else 0
        sigma = np.std(all_freqs)
        return ((M - sigma) / F_ps * 100) if F_ps > 0 else 0.0

    def _calc_gloominess_spectral(self) -> float:
        """e11: 频率均值偏离0.5的程度 → 忧郁度"""
        if not self.frequency_data:
            return 0.0
        all_freqs = np.concatenate(list(self.frequency_data)) if self.frequency_data else np.array([])
        if len(all_freqs) == 0:
            return 0.0
        sigma = np.std(all_freqs)
        M = np.mean(all_freqs)
        denom = 0.5 - M
        return (sigma / denom * 100) if abs(denom) > 0.0001 else 0.0

    def _calc_stability_spectral(self) -> float:
        """e14: 频率分布与正态分布的拟合度 → 稳定性"""
        if not self.frequency_data:
            return 0.0
        all_freqs = np.concatenate(list(self.frequency_data)) if self.frequency_data else np.array([])
        if len(all_freqs) < 10:
            return 50.0
        hist, bin_edges = np.histogram(all_freqs, bins=50, density=True)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        mu = np.mean(all_freqs)
        sigma = np.std(all_freqs)
        if sigma == 0:
            return 50.0
        normal_pdf = stats.norm.pdf(bin_centers, mu, sigma)
        sum_normal = np.sum(normal_pdf)
        sum_hist = np.sum(hist)
        K = sum_normal / sum_hist if sum_hist > 0 else 1
        error = np.sum((hist * K - normal_pdf) ** 2) / (np.sum(normal_pdf ** 2) + 1e-6)
        return 100 / (1 + error)

    # ================================================================
    #  时域替代方法（FPS < 3 时使用，适合低帧率拍照模式）
    # ================================================================

    def _calc_tension_time_domain(self) -> float:
        """e3 低频版：振动能量的「抖动率」——方向变化频次

        紧张的人面部肌肉僵硬但仍会有不自主抽动，表现为：
        振动能量时高时低、频繁改变方向（上升→下降交替）。

        计算：能量序列一阶差分的过零率（方向变化次数 / 总变化次数）
        """
        if len(self.vibration_energies) < 5:
            return 50.0
        energies = list(self.vibration_energies)
        diffs = np.diff(energies)
        if len(diffs) < 2:
            return 50.0
        # 方向变化：相邻两次差分的符号不同（乘积为负）
        sign_changes = sum(1 for i in range(1, len(diffs)) if diffs[i] * diffs[i - 1] < 0)
        jerk_rate = sign_changes / (len(diffs) - 1)  # 0~1
        # 映射：抖动率0.5 → 50分（正常），0→0（极度平稳），1→100（极度紧张）
        # 加上振幅大小的影响：能量波动幅度越大越紧张
        if np.mean(energies) > 0:
            cv = np.std(energies) / np.mean(energies)  # 变异系数
        else:
            cv = 0.0
        # 抖动率权重0.6，振幅波动权重0.4
        score = 0.6 * jerk_rate * 100 + 0.4 * min(cv * 50, 100)
        return score

    def _calc_energy_time_domain(self) -> float:
        """e7 低频版：振幅强度 × 规律性

        活力高的人：面部运动幅度适中且规律稳定。
        活力低的人：运动幅度小（无精打采）或幅度大但杂乱（焦躁不安）。

        计算：
        1. 振幅得分：A矩阵中活跃像素的均值（缩放到0-100）
        2. 规律得分：1 - 近期能量变异系数
        3. 活力 = 振幅得分 × 0.5 + 规律得分 × 0.5
        """
        # 振幅得分：从A矩阵提取
        amplitude_score = 50.0  # 默认中等
        if self.A_norm is not None:
            active = self.A_norm[self.A_norm > 0.05]  # 过滤噪声
            if len(active) > 50:  # 至少50个活跃像素才有效
                mean_ampl = float(np.mean(active))
                # mean_ampl 通常在0.05-0.3之间，映射到0-100
                amplitude_score = min(mean_ampl * 350, 100)

        # 规律得分：近期能量稳定性
        regularity_score = 50.0
        if len(self.vibration_energies) >= 4:
            recent = list(self.vibration_energies)[-8:]  # 最近8组能量
            if len(recent) >= 3 and np.mean(recent) > 0:
                cv = float(np.std(recent) / np.mean(recent))
                # cv=0（完全稳定）→100分，cv=1（极不稳定）→0分
                regularity_score = max(0, 100 - cv * 100)

        return amplitude_score * 0.5 + regularity_score * 0.5

    def _calc_gloominess_time_domain(self) -> float:
        """e11 低频版：振动能量的下降趋势

        情绪低落的人面部运动逐渐减少（越来越「懒得动」）。
        情绪正常的人面部运动保持稳定或有轻微波动。

        计算：最近能量序列的线性回归斜率
        负斜率（能量在下降）→ 忧郁升高
        正斜率或持平 → 忧郁低
        """
        if len(self.vibration_energies) < 8:
            return 50.0
        energies = np.array(list(self.vibration_energies)[-16:])  # 最近16组
        if len(energies) < 5:
            return 50.0

        x = np.arange(len(energies))
        if np.std(energies) < 1e-8:
            return 50.0

        slope, _ = np.polyfit(x, energies, 1)
        # 归一化斜率：slope / mean(energies) = 每步相对变化率
        mean_e = np.mean(energies)
        if mean_e > 0:
            norm_slope = slope / mean_e
        else:
            norm_slope = 0.0

        # norm_slope = -0.05（每步下降5%）→ 严重忧郁100分
        # norm_slope = 0（持平）→ 正常50分
        # norm_slope = +0.05（上升）→ 开朗0分
        gloom_score = 50 - norm_slope * 1000  # 斜率-0.05 → 50+50=100
        return max(0, min(100, gloom_score))

    def _calc_stability_time_domain(self) -> float:
        """e14 低频版：长期能量稳定性 vs 短期波动

        心理稳定的人：面部运动的能量水平长期保持平稳。
        心理不稳定的人：能量忽高忽低，长期和短期波动都大。

        计算：1 - (短期CV / 长期CV的比值)
        短期波动远大于长期趋势 → 不稳定
        """
        if len(self.vibration_energies) < 10:
            return 50.0

        energies = np.array(list(self.vibration_energies))
        mean_e = np.mean(energies)
        if mean_e == 0:
            return 50.0

        # 长期：全部历史
        long_cv = float(np.std(energies) / mean_e)

        # 短期：最近1/3
        split = max(len(energies) // 3, 3)
        recent = energies[-split:]
        recent_mean = np.mean(recent)
        if recent_mean > 0:
            short_cv = float(np.std(recent) / recent_mean)
        else:
            short_cv = 0.0

        # 短期波动越接近长期波动 → 越稳定
        if long_cv == 0:
            stability = 100.0
        else:
            ratio = short_cv / long_cv  # 0~∞，1表示短期=长期
            # ratio=1 → 100分，ratio=2 → 50分，ratio=4 → 0分
            stability = max(0, 100 - abs(ratio - 1) * 50)

        return stability

    # ================================================================
    #  主入口：处理单帧
    # ================================================================

    def process_frame(self, frame: np.ndarray, face_rect: tuple | None = None,
                      fps: float | None = None) -> dict | None:
        """处理单帧图像，返回 e1-e14 参数字典（缓冲区满时），否则返回 None

        Args:
            frame: BGR图像 (H, W, 3)
            face_rect: (x, y, w, h) 人脸边界框，None 时使用上次设置的人脸区域
            fps: 实际帧率，用于频率换算

        Returns:
            dict: {"e1":..., "e2":..., ..., "e14":..., "happiness_index":..., "happiness_level":...}
            None: 缓冲区未满，尚无结果
        """
        if fps is not None:
            self.fps = fps

        # 更新人脸区域
        if face_rect is not None:
            self.set_face_rect(*face_rect)

        if not self.face_initialized:
            return None

        # 预处理人脸区域
        preprocessed = self._preprocess_head_region(frame)
        if preprocessed is None:
            return None
        self.frame_buffer.append(preprocessed)

        # 缓冲区未满，暂不计算
        if len(self.frame_buffer) < self.accumulate_frames:
            self.frame_idx += 1
            return None

        # ---- 缓冲区满，开始计算 ----
        self.A, self.F = self._calculate_vibra_params()
        self._normalize_vibra_params()

        # 左右脸 ROI 分析
        lx, ly, lw, lh = self.left_face_rect
        rx, ry, rw, rh = self.right_face_rect
        h, w = frame.shape[:2]

        # 边界检查
        ly, lh = max(0, ly), min(lh, h - ly)
        ry, rh = max(0, ry), min(rh, h - ry)
        lx, lw = max(0, lx), min(lw, w - lx)
        rx, rw = max(0, rx), min(rw, w - rx)

        if lw > 0 and lh > 0 and rw > 0 and rh > 0:
            left_roi = frame[ly:ly + lh, lx:lx + lw]
            right_roi = frame[ry:ry + rh, rx:rx + rw]

            left_gray = cv2.cvtColor(left_roi, cv2.COLOR_BGR2GRAY) / 255.0
            right_gray = cv2.cvtColor(right_roi, cv2.COLOR_BGR2GRAY) / 255.0

            left_ampl = float(np.sum(np.abs(left_gray - np.mean(left_gray))))
            right_ampl = float(np.sum(np.abs(right_gray - np.mean(right_gray))))
            left_freq = float(np.max(left_gray)) if np.max(left_gray) > 0 else 0.001
            right_freq = float(np.max(right_gray)) if np.max(right_gray) > 0 else 0.001
        else:
            left_ampl = right_ampl = 0.0
            left_freq = right_freq = 0.001

        energy = float(np.sum(self.A ** 2)) if self.A is not None and self.A.size > 0 else 0.0

        self.vibration_energies.append(energy)
        self.left_amplitudes.append(left_ampl)
        self.right_amplitudes.append(right_ampl)
        self.left_max_freqs.append(left_freq)
        self.right_max_freqs.append(right_freq)

        # 频谱分析 — 每 time_window 帧做一次 Welch
        if self.frame_idx % self.time_window == 0 and len(self.vibration_energies) >= self.time_window:
            energy_arr = np.array(list(self.vibration_energies)[-self.time_window:])
            try:
                freqs, psd = signal.welch(energy_arr, self.fps, nperseg=min(self.time_window, len(energy_arr) - 1))
                self.frequency_data.append(freqs)
                self.power_spectrum.append(psd)
            except Exception:
                pass

        # 计算14参数
        results = self._calculate_all_parameters()

        # 附加幸福指数分级
        happiness_index = results.get("e12", 0)
        if happiness_index >= 80:
            happiness_level = "高"
        elif happiness_index >= 60:
            happiness_level = "中"
        else:
            happiness_level = "低"

        if happiness_index >= 70:
            safety_risk = "低风险"
        elif happiness_index >= 40:
            safety_risk = "中风险"
        else:
            safety_risk = "高风险"

        self.latest_results = {
            **results,
            "happiness_index": happiness_index,
            "happiness_level": happiness_level,
            "safety_risk": safety_risk,
        }

        self.frame_idx += 1
        return self.latest_results

    def get_results(self) -> dict | None:
        """获取最近一次计算结果（不处理新帧）"""
        return self.latest_results
