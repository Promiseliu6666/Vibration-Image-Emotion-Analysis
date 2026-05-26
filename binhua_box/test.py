"""
RTSP 视频测试 — ffmpeg 解码 + 缩放 → OpenCV X11 显示。

ffmpeg 负责 RTSP 拉流 + H.264 多线程解码 + 缩放，
OpenCV 只做 cv2.imshow，不做解码。

用法:
    python test.py rtsp://admin:pass@192.168.3.6:554/main/h264/av_stream
    python test.py rtsp://... --scale 0.3 --fps 15
    python test.py --source camera      # USB 摄像头
    python test.py --source pattern     # 测试画面
"""
import argparse
import os
import subprocess
import sys
import time

import cv2
import numpy as np


def run_rtsp(source: str, scale: float, fps: int) -> None:
    """ffmpeg 解码 RTSP + 缩放 → 管道 → OpenCV X11 显示。"""
    if "DISPLAY" not in os.environ:
        print("[ERROR] 未检测到 DISPLAY，请用 MobaXterm SSH 连接")
        sys.exit(1)

    # 先探一下原始分辨率
    cap = cv2.VideoCapture(source)
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    if not cap.isOpened():
        print(f"[ERROR] 无法打开: {source}")
        sys.exit(1)
    src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    w = int(src_w * scale)
    h = int(src_h * scale)

    print(f"[INFO] RTSP: {source}")
    print(f"[INFO] 原始: {src_w}x{src_h} → 显示: {w}x{h} @ {fps}fps")
    print(f"[INFO] DISPLAY: {os.environ['DISPLAY']}")
    print("[INFO] 按 'q' 或 ESC 退出")

    # ffmpeg 解码 + 缩放 → rawvideo stdout
    proc = subprocess.Popen([
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-threads", "4",
        "-i", source,
        "-vf", f"fps={fps},scale={w}:{h}",
        "-pix_fmt", "bgr24",
        "-f", "rawvideo",
        "-loglevel", "error",
        "pipe:1",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    win = f"RTSP - {w}x{h}"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, w, h)

    frame_size = w * h * 3
    frame_count = 0
    start_time = time.time()

    try:
        while True:
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                err = proc.stderr.read(512).decode(errors="replace")
                if err:
                    print(f"[WARN] ffmpeg: {err.strip()}")
                print("[INFO] 流中断，重连...")
                time.sleep(2)
                proc.terminate()
                proc = subprocess.Popen([
                    "ffmpeg",
                    "-rtsp_transport", "tcp",
                    "-threads", "4",
                    "-i", source,
                    "-vf", f"fps={fps},scale={w}:{h}",
                    "-pix_fmt", "bgr24",
                    "-f", "rawvideo",
                    "-loglevel", "error",
                    "pipe:1",
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                continue

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((h, w, 3))

            frame_count += 1
            elapsed = time.time() - start_time
            rate = frame_count / elapsed if elapsed > 0 else 0
            cv2.putText(frame, f"FPS: {rate:.1f}", (w - 130, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.imshow(win, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        cv2.destroyAllWindows()
        if frame_count:
            elapsed = time.time() - start_time
            print(f"[INFO] {frame_count} 帧, {elapsed:.1f}s, "
                  f"平均 {frame_count / elapsed:.1f} fps")


def run_camera(width: int, height: int) -> None:
    """USB 摄像头 → ffplay V4L2 → X11。"""
    if "DISPLAY" not in os.environ:
        print("[ERROR] 未检测到 DISPLAY，请用 MobaXterm SSH 连接")
        sys.exit(1)
    print(f"[INFO] USB 摄像头 /dev/video0 → {width}x{height}")
    print("[INFO] 按 'q' 或 ESC 退出")
    subprocess.run([
        "ffplay",
        "-f", "v4l2",
        "-video_size", f"{width}x{height}",
        "-x", str(width), "-y", str(height),
        "-window_title", "USB Camera",
        "-loglevel", "quiet",
        "/dev/video0",
    ])


def run_pattern(width: int, height: int, fps: int) -> None:
    """OpenCV 生成测试画面 → X11。"""
    if "DISPLAY" not in os.environ:
        print("[ERROR] 未检测到 DISPLAY，请用 MobaXterm SSH 连接")
        sys.exit(1)
    print(f"[INFO] 测试画面 {width}x{height} @ {fps}fps")
    print("[INFO] 按 'q' 或 ESC 退出")

    win = "Test - pattern"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, width, height)

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:] = (40, 40, 60)
            t = time.time()

            x = int((np.sin(t * 1.5) * 0.4 + 0.5) * (width - 120))
            y = int((np.cos(t * 1.3) * 0.4 + 0.5) * (height - 90))
            cv2.rectangle(frame, (x, y), (x + 120, y + 90), (0, 200, 255), -1)
            cx = int((np.cos(t * 0.7) * 0.4 + 0.5) * width)
            cy = int((np.sin(t * 0.9) * 0.4 + 0.5) * height)
            cv2.circle(frame, (cx, cy), 30, (0, 255, 100), -1)

            elapsed = time.time() - start_time
            cv2.putText(frame, time.strftime("%Y-%m-%d %H:%M:%S"),
                        (10, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"FPS: {frame_count / elapsed:.1f}" if elapsed > 0 else "FPS: --",
                        (width - 130, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            cv2.imshow(win, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break

            frame_count += 1
            expected = frame_count / fps
            if elapsed < expected:
                time.sleep(expected - elapsed)

    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
        if frame_count:
            elapsed = time.time() - start_time
            print(f"[INFO] {frame_count} 帧, {elapsed:.1f}s, "
                  f"平均 {frame_count / elapsed:.1f} fps")


def main():
    parser = argparse.ArgumentParser(description="RTSP 视频测试")
    parser.add_argument("source", nargs="?", default="pattern",
                        help="RTSP 地址 / 'pattern' / 'camera' / 视频文件")
    parser.add_argument("--scale", type=float, default=0.4,
                        help="缩放比例 (默认: 0.4, 仅 RTSP)")
    parser.add_argument("--fps", type=int, default=15,
                        help="输出帧率 (默认: 15, 仅 RTSP/pattern)")
    parser.add_argument("--width", type=int, default=640,
                        help="宽度 (默认: 640, 仅 pattern/camera)")
    parser.add_argument("--height", type=int, default=480,
                        help="高度 (默认: 480, 仅 pattern/camera)")
    parser.add_argument("-s", "--source", dest="source_opt", default=None,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.source_opt:
        args.source = args.source_opt

    if args.source in ("pattern",):
        run_pattern(args.width, args.height, args.fps)
    elif args.source in ("camera",):
        run_camera(args.width, args.height)
    else:
        run_rtsp(args.source, args.scale, args.fps)


if __name__ == "__main__":
    main()
