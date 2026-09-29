// Định vị thật bằng Geolocation API. Chỉ bắt đầu khi người dùng bấm, dừng bằng clearWatch.
// Không lưu lịch sử vị trí. Lỗi được báo lên, không tự chuyển sang mô phỏng.

const ERROR_MESSAGES = {
  1: "Bạn đã từ chối quyền vị trí. Có thể bật Mô phỏng để trình diễn.",
  2: "Trình duyệt không xác định được vị trí.",
  3: "Quá thời gian chờ vị trí; vẫn đang thử tiếp.",
};

export class GpsTracker {
  constructor({ onPosition, onStatus }) {
    this.onPosition = onPosition;
    this.onStatus = onStatus;
    this.watchId = null;
  }

  get active() {
    return this.watchId !== null;
  }

  start() {
    if (!("geolocation" in navigator)) {
      this.onStatus({ type: "error", message: "Trình duyệt không hỗ trợ định vị." });
      return false;
    }
    if (!window.isSecureContext) {
      this.onStatus({ type: "error", message: "Định vị cần HTTPS hoặc localhost." });
      return false;
    }
    this.onStatus({ type: "waiting", message: "Đang chờ trình duyệt cấp vị trí…" });
    this.watchId = navigator.geolocation.watchPosition(
      (pos) =>
        this.onPosition({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          timestamp: pos.timestamp,
          mode: "gps",
        }),
      (err) => {
        if (err.code === 1) this.stop();
        this.onStatus({ type: "error", message: ERROR_MESSAGES[err.code] ?? "Lỗi định vị không xác định." });
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 },
    );
    return true;
  }

  stop() {
    if (this.watchId !== null) navigator.geolocation.clearWatch(this.watchId);
    this.watchId = null;
  }
}
