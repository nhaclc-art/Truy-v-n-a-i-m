// Bảng trượt (bottom sheet) cho màn hình hẹp: bản đồ phủ toàn màn hình, danh sách nằm trong bảng
// có ba mức cao peek / half / full. Chạm tay cầm để chuyển mức, kéo tay cầm để chỉnh rồi bắt về mức gần nhất.
// Trên màn hình rộng, lớp này không làm gì: bảng điều khiển là cột bên trái như cũ.

const NARROW = window.matchMedia("(max-width: 900px)");
const STATES = ["peek", "half", "full"];
const DRAG_THRESHOLD_PX = 6;

export class BottomSheet {
  // panel: phần tử cuộn chứa danh sách; handle: tay cầm; peekUntil: phần tử cuối cùng còn thấy ở mức peek.
  constructor(panel, handle, peekUntil, onResize) {
    this.panel = panel;
    this.handle = handle;
    this.peekUntil = peekUntil;
    this.onResize = onResize;
    this.state = "half";
    this.drag = null;
    this.suppressClick = false;
    this.savedScroll = 0;

    handle.addEventListener("pointerdown", (e) => this.startDrag(e));
    handle.addEventListener("pointermove", (e) => this.moveDrag(e));
    handle.addEventListener("pointerup", () => this.endDrag());
    handle.addEventListener("pointercancel", () => this.endDrag());
    handle.addEventListener("click", () => {
      if (this.suppressClick) {
        this.suppressClick = false;
        return;
      }
      this.set(this.state === "peek" ? "half" : this.state === "half" ? "full" : "peek");
    });
    NARROW.addEventListener("change", () => this.apply());
    window.addEventListener("resize", () => this.apply());
    this.apply();
  }

  get enabled() {
    return NARROW.matches;
  }

  heights() {
    const viewport = window.innerHeight;
    const panelTop = this.panel.getBoundingClientRect().top;
    const peek = Math.round(this.peekUntil.getBoundingClientRect().bottom - panelTop + this.panel.scrollTop + 12);
    const header = document.querySelector(".appbar").offsetHeight;
    return { peek, half: Math.max(peek, Math.round(viewport * 0.5)), full: Math.max(peek, viewport - header - 56) };
  }

  set(state) {
    if (!this.enabled || state === this.state) return;
    // Ở mức peek chỉ còn thấy ô tìm kiếm nên cuộn về đầu; nhớ vị trí cũ để mở lại đúng chỗ đang xem.
    if (state === "peek") this.savedScroll = this.panel.scrollTop;
    const restore = this.state === "peek" ? this.savedScroll : 0;
    this.state = state;
    this.apply();
    if (restore) this.panel.scrollTop = restore;
  }

  // Ghi chiều cao hiện tại vào biến CSS --sheet-h để nút nổi, chú giải và ghi nguồn bản đồ nằm trên bảng.
  setHeight(px) {
    this.panel.style.height = `${px}px`;
    document.documentElement.style.setProperty("--sheet-h", `${px}px`);
  }

  apply() {
    if (!this.enabled) {
      this.panel.style.removeProperty("height");
      delete this.panel.dataset.sheet;
      document.documentElement.style.setProperty("--sheet-h", "0px");
      this.onResize(0);
      return;
    }
    const height = this.heights()[this.state];
    this.setHeight(height);
    this.panel.dataset.sheet = this.state;
    if (this.state === "peek") this.panel.scrollTop = 0;
    this.onResize(height);
  }

  startDrag(e) {
    if (!this.enabled) return;
    this.drag = { y: e.clientY, height: this.panel.getBoundingClientRect().height, moved: false };
    this.handle.setPointerCapture(e.pointerId);
  }

  moveDrag(e) {
    if (!this.drag) return;
    const dy = this.drag.y - e.clientY;
    if (!this.drag.moved && Math.abs(dy) < DRAG_THRESHOLD_PX) return;
    this.drag.moved = true;
    this.panel.classList.add("dragging");
    const { peek, full } = this.heights();
    this.setHeight(Math.min(full, Math.max(peek, this.drag.height + dy)));
  }

  endDrag() {
    if (!this.drag) return;
    const moved = this.drag.moved;
    this.drag = null;
    this.panel.classList.remove("dragging");
    if (!moved) return;
    // Có trình duyệt phát click sau khi kéo, có trình duyệt không: chỉ chặn click ngay sau lần kéo này.
    this.suppressClick = true;
    setTimeout(() => {
      this.suppressClick = false;
    }, 0);
    const current = this.panel.getBoundingClientRect().height;
    const heights = this.heights();
    this.state = STATES.reduce((best, s) => (Math.abs(heights[s] - current) < Math.abs(heights[best] - current) ? s : best));
    this.apply();
  }
}
