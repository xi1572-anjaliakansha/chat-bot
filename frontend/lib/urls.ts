/** FastAPI base (no trailing slash). For reference / server-side use. */
function backendOrigin(): string {
  const raw =
    process.env.NEXT_PUBLIC_BACKEND_URL?.trim() || "http://127.0.0.1:8000";
  return raw.replace(/0\.0\.0\.0/g, "127.0.0.1").replace(/\/$/, "");
}

export const BACKEND_ORIGIN = backendOrigin();
/** Direct FastAPI URLs — browser fetch() needs matching CORS on the backend. */
export const UPLOAD_URL = `${BACKEND_ORIGIN}/upload`;
export const CHAT_URL = `${BACKEND_ORIGIN}/chat`;
