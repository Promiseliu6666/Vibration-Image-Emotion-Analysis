"""
Face happiness (vibraimage) analysis engine — adapted for box runtime.
Pure Python, depends on numpy, scipy, opencv-python.
"""
import cv2
import numpy as np
from scipy import ndimage, signal
import scipy.stats as stats


class VibraimageCore:
    """Real-time facial micro-vibration analysis. Accepts face_rect from external detector."""

    def __init__(self):
        self.FIXED_WIDTH = 640
        self.FIXED_HEIGHT = 480
        self.FIXED_RESOLUTION = (self.FIXED_WIDTH, self.FIXED_HEIGHT)
        self.halo_params = {
            "FACE_DILATE_RATIO": 1.3,
            "NOISE_THRESHOLD": 0.001,
            "ACCUMULATE_FRAMES": 50,
        }
        self.time_window = 20
        self.fps = 30
        self.vibration_energies = []
        self.left_amplitudes = []
        self.right_amplitudes = []
        self.left_max_freqs = []
        self.right_max_freqs = []
        self.frequency_data = []
        self.power_spectrum = []
        self.frame_buffer = []
        self.A = None
        self.F = None
        self.A_norm = None
        self.F_norm = None
        self.face_rect = None
        self.left_face_rect = None
        self.right_face_rect = None
        self.e1_history = []
        self.e2_history = []
        self.e3_history = []
        self.e4_history = []
        self.e5_history = []
        self.e6_history = []
        self.e7_history = []
        self.e8_history = []
        self.e9_history = []
        self.e10_history = []
        self.e11_history = []
        self.e12_history = []
        self.e13_history = []
        self.e14_history = []
        self.frame_idx = 0
        self.first_frame = True

    def reset(self):
        self.vibration_energies = []
        self.left_amplitudes = []
        self.right_amplitudes = []
        self.left_max_freqs = []
        self.right_max_freqs = []
        self.frequency_data = []
        self.power_spectrum = []
        self.frame_buffer = []
        self.A = None
        self.F = None
        self.A_norm = None
        self.F_norm = None
        self.face_rect = None
        self.left_face_rect = None
        self.right_face_rect = None
        self.e1_history = []
        self.e2_history = []
        self.e3_history = []
        self.e4_history = []
        self.e5_history = []
        self.e6_history = []
        self.e7_history = []
        self.e8_history = []
        self.e9_history = []
        self.e10_history = []
        self.e11_history = []
        self.e12_history = []
        self.e13_history = []
        self.e14_history = []
        self.frame_idx = 0
        self.first_frame = True

    def _preprocess_head_region(self, frame_640, face_rect):
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
        return A, F

    def _normalize_vibra_params(self):
        if self.A is not None:
            a_min, a_max = self.A.min(), self.A.max()
            self.A_norm = (self.A - a_min) / (a_max - a_min + 1e-6) if a_max > a_min else np.zeros_like(self.A)
        if self.F is not None:
            f_min, f_max = self.F.min(), self.F.max()
            self.F_norm = (self.F - f_min) / (f_max - f_min + 1e-6) if f_max > f_min else np.zeros_like(self.F)

    def _calculate_all_parameters(self):
        results = {}

        if self.vibration_energies:
            energies = np.array(self.vibration_energies)
            mean_energy = np.mean(energies)
            std_energy = np.std(energies)
            max_energy = np.max(energies) if len(energies) > 0 else 1
            e1 = (mean_energy + std_energy) / max_energy * 100 if max_energy != 0 else 0
        else:
            e1 = 0
        results["e1"] = round(max(0, min(100, e1)), 2)
        self.e1_history.append(results["e1"])

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
                    A_max = max(A_L, A_R) if max(A_L, A_R) > 0 else 1
                    F_max = max(F_L, F_R) if max(F_L, F_R) > 0 else 1
                    sum_val += (abs(A_L - A_R) / A_max + abs(F_L - F_R) / F_max)
                e2 = (sum_val / (2 * n)) * 100
        results["e2"] = round(max(0, min(100, e2)), 2)
        self.e2_history.append(results["e2"])

        e3 = 0
        if self.power_spectrum and self.frequency_data:
            lengths = [len(p) for p in self.power_spectrum]
            if lengths:
                most_common_len = max(set(lengths), key=lengths.count)
                valid_psd = [p for p, f in zip(self.power_spectrum, self.frequency_data) if len(p) == most_common_len]
                valid_freq = [f for f in self.frequency_data if len(f) == most_common_len]
                if valid_psd:
                    avg_psd = np.mean(valid_psd, axis=0)
                    avg_freq = np.mean(valid_freq, axis=0)
                    f_max = np.max(avg_freq) if avg_freq.size > 0 else 1
                    high_power = np.sum(avg_psd[avg_freq >= f_max / 2])
                    total_power = np.sum(avg_psd[avg_freq >= 0.1])
                    e3 = (high_power / total_power * 100) if total_power > 0 else 0
        results["e3"] = round(max(0, min(100, e3)), 2)
        self.e3_history.append(results["e3"])

        e4 = (results["e1"] + results["e2"] + results["e3"]) / 3
        results["e4"] = round(e4, 2)
        self.e4_history.append(results["e4"])

        e5 = 100
        if self.vibration_energies:
            energies = np.array(self.vibration_energies)
            mean_e = np.mean(energies)
            if mean_e > 0:
                Va = np.std(energies) / mean_e
                e5 = max(0, min(100, 100 - 2 * Va * 100))
        results["e5"] = round(e5, 2)
        self.e5_history.append(results["e5"])

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
                e6 = 100 - e6
        results["e6"] = round(max(0, min(100, e6)), 2)
        self.e6_history.append(results["e6"])

        e7 = 0
        if self.frequency_data:
            all_freqs = np.concatenate(self.frequency_data) if self.frequency_data else np.array([])
            if len(all_freqs) > 0:
                F_ps = np.max(all_freqs)
                freq_counts = np.bincount(np.round(all_freqs).astype(int))
                M = np.max(freq_counts) if len(freq_counts) > 0 else 0
                sigma = np.std(all_freqs)
                e7 = ((M - sigma) / F_ps * 100) if F_ps > 0 else 0
        results["e7"] = round(max(0, min(100, e7)), 2)
        self.e7_history.append(results["e7"])

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

        e9 = (results["e1"] + results["e5"]) / 2
        results["e9"] = round(e9, 2)
        self.e9_history.append(results["e9"])

        e10 = (results["e2"] + results["e3"]) / 2
        results["e10"] = round(e10, 2)
        self.e10_history.append(results["e10"])

        e11 = 0
        if self.frequency_data:
            all_freqs = np.concatenate(self.frequency_data) if self.frequency_data else np.array([])
            if len(all_freqs) > 0:
                sigma = np.std(all_freqs)
                M = np.mean(all_freqs)
                denom = 0.5 - M
                if denom > 0.0001:
                    e11 = sigma / denom * 100
        results["e11"] = round(max(0, min(100, e11)), 2)
        self.e11_history.append(results["e11"])

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

        e13 = 50
        if len(self.e8_history) >= 2 and len(self.e7_history) >= 2:
            e8_arr = np.array(self.e8_history)
            e7_arr = np.array(self.e7_history)
            std_e8 = np.std(e8_arr)
            std_e7 = np.std(e7_arr)
            if std_e8 == 0 or std_e7 == 0:
                r = 1.0 if (std_e8 == 0 and std_e7 == 0) else 0.0
            else:
                r, _ = stats.pearsonr(e8_arr, e7_arr)
            e13 = (r + 1) / 2 * 100
        results["e13"] = round(max(0, min(100, e13)), 2)
        self.e13_history.append(results["e13"])

        e14 = 0
        if self.frequency_data:
            all_freqs = np.concatenate(self.frequency_data) if self.frequency_data else np.array([])
            if len(all_freqs) > 10:
                hist, bin_edges = np.histogram(all_freqs, bins=50, density=True)
                bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
                mu = np.mean(all_freqs)
                sigma = np.std(all_freqs)
                if sigma > 0:
                    normal_pdf = stats.norm.pdf(bin_centers, mu, sigma)
                    sum_normal = np.sum(normal_pdf)
                    sum_hist = np.sum(hist)
                    K = sum_normal / sum_hist if sum_hist > 0 else 1
                    error = np.sum((hist * K - normal_pdf)**2) / (np.sum(normal_pdf**2) + 1e-6)
                    e14 = 100 / (1 + error)
        results["e14"] = round(max(0, min(100, e14)), 2)
        self.e14_history.append(results["e14"])

        return results

    def process_frame(self, frame, face_rect=None, fps=None):
        """Process a single frame. face_rect must be provided by external detector."""
        if fps is not None:
            self.fps = fps

        if self.first_frame:
            if face_rect is None:
                return None
            x, y, w, h = face_rect
            self.face_rect = (x, y, w, h)
            center_x = x + w // 2
            self.left_face_rect = (x, y, w // 2, h)
            self.right_face_rect = (center_x, y, w - w // 2, h)
            self.first_frame = False

        preprocessed, _ = self._preprocess_head_region(frame, self.face_rect)
        self.frame_buffer.append(preprocessed)
        if len(self.frame_buffer) > self.halo_params['ACCUMULATE_FRAMES']:
            self.frame_buffer.pop(0)

        results = None
        if len(self.frame_buffer) == self.halo_params['ACCUMULATE_FRAMES']:
            self.A, self.F = self._calculate_vibra_params(self.frame_buffer)
            self._normalize_vibra_params()

            lx, ly, lw, lh = self.left_face_rect
            rx, ry, rw, rh = self.right_face_rect
            left_roi = frame[ly:ly + lh, lx:lx + lw]
            right_roi = frame[ry:ry + rh, rx:rx + rw]
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

            if self.frame_idx % self.time_window == 0 and len(self.vibration_energies) >= self.time_window:
                energy_arr = np.array(self.vibration_energies[-self.time_window:])
                freqs, psd = signal.welch(energy_arr, self.fps, nperseg=min(self.time_window, 1024))
                self.frequency_data.append(freqs)
                self.power_spectrum.append(psd)

            results = self._calculate_all_parameters()

        self.frame_idx += 1
        return results
