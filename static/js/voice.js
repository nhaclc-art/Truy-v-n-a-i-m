// Tìm bằng giọng nói qua Web Speech API của trình duyệt, tiếng Việt (vi-VN).
// Chrome/Edge (máy tính, Android) và Safari (iOS 14.5+) gửi âm thanh tới dịch vụ nhận dạng của hãng
// trình duyệt, nên cần Internet. Chỉ chạy trong môi trường an toàn (HTTPS hoặc localhost) và khi người
// dùng cho phép micro. Firefox không hỗ trợ: nút micro bị ẩn.
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// "ok" | "unsupported" (trình duyệt không có API) | "insecure" (trang không chạy qua HTTPS/localhost)
export function voiceSupport() {
  if (!Recognition) return "unsupported";
  return window.isSecureContext ? "ok" : "insecure";
}

export const VOICE_ERRORS = {
  "not-allowed": "Trình duyệt chặn micro. Cho phép micro cho trang này rồi thử lại.",
  "service-not-allowed": "Trình duyệt không cho dùng dịch vụ nhận giọng nói trên trang này.",
  "no-speech": "Không nghe thấy gì. Bấm micro rồi nói ngay.",
  "audio-capture": "Không tìm thấy micro trên thiết bị.",
  network: "Nhận giọng nói cần Internet (âm thanh được gửi tới dịch vụ nhận dạng của trình duyệt).",
  "language-not-supported": "Trình duyệt chưa hỗ trợ nhận giọng nói tiếng Việt.",
};

export class VoiceSearch {
  constructor({ lang = "vi-VN", onInterim, onFinal, onError, onStateChange }) {
    this.lang = lang;
    this.onInterim = onInterim;
    this.onFinal = onFinal;
    this.onError = onError;
    this.onStateChange = onStateChange;
    this.rec = null;
  }

  get listening() {
    return this.rec !== null;
  }

  start() {
    if (this.rec) return;
    const rec = new Recognition();
    rec.lang = this.lang;
    rec.interimResults = true;
    rec.maxAlternatives = 3;
    rec.continuous = false;
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const alternatives = Array.from({ length: result.length }, (_, j) => ({
            transcript: result[j].transcript.trim(),
            confidence: result[j].confidence,
          })).filter((a) => a.transcript);
          if (alternatives.length) this.onFinal(alternatives);
        } else {
          interim += result[0].transcript;
        }
      }
      if (interim.trim()) this.onInterim(interim.trim());
    };
    rec.onerror = (event) => {
      if (event.error !== "aborted") this.onError(event.error);
    };
    rec.onend = () => {
      this.rec = null;
      this.onStateChange(false);
    };
    this.rec = rec;
    try {
      rec.start();
      this.onStateChange(true);
    } catch (err) {
      this.rec = null;
      this.onError(err.name || "start-failed");
    }
  }

  stop() {
    this.rec?.stop();
  }
}
