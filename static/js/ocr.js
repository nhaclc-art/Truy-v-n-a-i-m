// Đọc chữ trên ảnh biển hiệu bằng Tesseract.js, chạy hoàn toàn trong trình duyệt (Web Worker +
// WebAssembly). Ảnh không gửi lên máy chủ; chỉ chữ đọc được mới được gửi để dựng truy vấn.
// Bộ đọc chữ (~12 MB) nằm ở static/vendor/tesseract, tải bằng `python -m scripts.vendor_tesseract`,
// và chỉ được nạp khi người dùng chọn ảnh lần đầu.
const BASE = "/static/vendor/tesseract";
const MAX_SIDE_PX = 1600; // ảnh điện thoại 12 MP thu nhỏ để đọc nhanh; biển hiệu vẫn đủ nét

const STAGES = {
  "loading tesseract core": "Đang nạp bộ đọc chữ",
  "initializing tesseract": "Đang khởi động bộ đọc chữ",
  "loading language traineddata": "Đang nạp dữ liệu tiếng Việt, tiếng Anh",
  "loading language traineddata (from cache)": "Đang nạp dữ liệu (đã lưu)",
  "initializing api": "Đang khởi động",
  "recognizing text": "Đang đọc chữ",
};

let scriptPromise = null;
let workerPromise = null;
let progressHandler = null;

export class OcrMissingError extends Error {}

function loadScript() {
  if (window.Tesseract) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = `${BASE}/tesseract.min.js`;
      script.onload = resolve;
      script.onerror = () => {
        scriptPromise = null;
        reject(new OcrMissingError("Chưa cài bộ đọc chữ: chạy python -m scripts.vendor_tesseract rồi tải lại trang."));
      };
      document.head.append(script);
    });
  }
  return scriptPromise;
}

function getWorker() {
  if (!workerPromise) {
    workerPromise = loadScript()
      .then(() =>
        window.Tesseract.createWorker(["vie", "eng"], 1, {
          workerPath: `${BASE}/worker.min.js`,
          corePath: `${BASE}/core`,
          langPath: `${BASE}/lang`,
          // Tạo worker từ file cùng nguồn (không dùng blob:) để hợp CSP của ứng dụng.
          workerBlobURL: false,
          logger: (m) => progressHandler?.({ stage: STAGES[m.status] ?? m.status, progress: m.progress ?? 0 }),
        }),
      )
      .catch((err) => {
        workerPromise = null;
        throw err;
      });
  }
  return workerPromise;
}

// Thu nhỏ ảnh (giữ tỷ lệ, xoay theo EXIF) vào canvas trước khi đọc.
async function toCanvas(file) {
  let bitmap;
  try {
    bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    bitmap = await createImageBitmap(file); // trình duyệt cũ không nhận tùy chọn xoay ảnh
  }
  const scale = Math.min(1, MAX_SIDE_PX / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d").drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();
  return canvas;
}

// Trả {text, confidence (0–100), ms}. onProgress nhận {stage, progress 0–1}.
export async function readImage(file, onProgress) {
  progressHandler = onProgress;
  const started = performance.now();
  const [worker, canvas] = await Promise.all([getWorker(), toCanvas(file)]);
  const { data } = await worker.recognize(canvas);
  return { text: data.text ?? "", confidence: data.confidence ?? 0, ms: Math.round(performance.now() - started) };
}
