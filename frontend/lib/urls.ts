/**
 * FastAPI base URL (browser). Set NEXT_PUBLIC_BACKEND_URL in .env, e.g.
 * http://127.0.0.1:8000 — not 0.0.0.0. Backend CORS must allow your Next
 * origin (e.g. http://localhost:3000).
 */
function backendOrigin(): string {
  const raw =
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "http://127.0.0.1:8000";
  return raw.replace(/0\.0\.0\.0/g, "127.0.0.1").replace(/\/$/, "");
}

export const BACKEND_ORIGIN = backendOrigin();
export const UPLOAD_URL = `${BACKEND_ORIGIN}/upload`;
export const CHAT_URL = `${BACKEND_ORIGIN}/chat`;
