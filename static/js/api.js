// Gọi API JSON của backend; lỗi HTTP được chuyển thành Error kèm thông điệp từ server.
export async function getJSON(url, { signal } = {}) {
  const resp = await fetch(url, { signal, headers: { Accept: "application/json" } });
  let body = null;
  try {
    body = await resp.json();
  } catch {
    // Phản hồi không phải JSON (ví dụ proxy lỗi): dùng mã HTTP làm thông điệp.
  }
  if (!resp.ok) {
    const err = new Error(body?.error || `HTTP ${resp.status}`);
    err.status = resp.status;
    err.body = body;
    throw err;
  }
  return body;
}
