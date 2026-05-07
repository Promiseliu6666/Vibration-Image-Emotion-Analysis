import cv2

# ==================== 指定外接 USB 摄像头 ====================
camera_index = 2         # ←←← 这里改成你扫描到的 UQSB 摄像头索引！！！

cap = cv2.VideoCapture(camera_index)

# Windows 用户如果画面卡顿，改成下面这行
# cap = cv2.VideoCapture(camera_
# index, cv2.CAP_DSHOW)

if not cap.isOpened():
    print(f"❌ 无法打开索引 {camera_index} 的摄像头！")
    print("请确认：")
    print("   1. USB 摄像头已插入")
    print("   2. 没有被其他软件占用")
    print("   3. 再次运行扫描脚本确认索引")
    exit()

print(f"✅ 已成功打开索引 {camera_index} 的摄像头（外接 USB）")
print("   按键盘【q】键退出")

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ 无法读取画面")
        break

    # 可选：加个标题显示当前索引
    cv2.putText(frame, f"Camera Index: {camera_index} (USB)", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow(f'USB摄像头实时画面 - 索引 {camera_index}（按 q 退出）', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("程序已退出 👋")