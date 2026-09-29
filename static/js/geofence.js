// Geofence cho một POI, chỉ chạy khi trang đang mở và nhận được mẫu vị trí.
// Trạng thái UNKNOWN / OUTSIDE / INSIDE, trễ biên: vào khi d ≤ enter_m, ra khi d ≥ exit_m
// (vùng giữa giữ trạng thái cũ). Cần confirm_samples mẫu liên tiếp để đổi trạng thái; mẫu có
// accuracy > max_accuracy_m bị bỏ qua. Cooldown chỉ chặn thông báo, không chặn ghi nhận sự kiện.
// Không phụ thuộc DOM để test được bằng `node --test`.

export const UNKNOWN = "UNKNOWN";
export const OUTSIDE = "OUTSIDE";
export const INSIDE = "INSIDE";

const EARTH_RADIUS_M = 6371008.8; // cùng bán kính với src/geo.py

export function haversineM(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dphi = (lat2 - lat1) * rad;
  const dlmb = (lon2 - lon1) * rad;
  const a = Math.sin(dphi / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dlmb / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(Math.min(1, a)));
}

export class Geofence {
  // target: {id, name, lat, lon}; config: {enter_m, exit_m, confirm_samples, cooldown_s, max_accuracy_m}
  constructor(target, config) {
    this.target = target;
    this.config = config;
    this.reset();
  }

  reset() {
    this.state = UNKNOWN;
    this.pending = null;
    this.lastNotifiedAt = null;
  }

  // sample: {lat, lon, accuracy (m hoặc null), timestamp (ms), mode}
  update(sample) {
    const { enter_m, exit_m, confirm_samples, cooldown_s, max_accuracy_m } = this.config;
    const distance = haversineM(sample.lat, sample.lon, this.target.lat, this.target.lon);
    const result = { state: this.state, distance_m: distance, event: null, initialized: false, lowAccuracy: false, pending: null };

    if (sample.accuracy != null && sample.accuracy > max_accuracy_m) {
      this.pending = null; // mẫu kém làm đứt chuỗi mẫu liên tiếp
      return { ...result, lowAccuracy: true };
    }

    if (this.state === UNKNOWN) {
      // Mẫu đầu chỉ khởi tạo trạng thái, không coi là vừa đi vào hay đi ra.
      this.state = distance <= enter_m ? INSIDE : OUTSIDE;
      return { ...result, state: this.state, initialized: true };
    }

    let next = null;
    if (this.state === OUTSIDE && distance <= enter_m) next = INSIDE;
    else if (this.state === INSIDE && distance >= exit_m) next = OUTSIDE;
    if (next === null) {
      this.pending = null;
      return result;
    }

    const count = this.pending?.to === next ? this.pending.count + 1 : 1;
    if (count < confirm_samples) {
      this.pending = { to: next, count };
      return { ...result, pending: { to: next, count, needed: confirm_samples } };
    }

    this.state = next;
    this.pending = null;
    const notified = this.lastNotifiedAt === null || sample.timestamp - this.lastNotifiedAt >= cooldown_s * 1000;
    if (notified) this.lastNotifiedAt = sample.timestamp;
    return {
      ...result,
      state: this.state,
      event: {
        type: next === INSIDE ? "enter" : "exit",
        poiId: this.target.id,
        poiName: this.target.name,
        at: sample.timestamp,
        mode: sample.mode,
        distance_m: distance,
        notified,
      },
    };
  }
}
