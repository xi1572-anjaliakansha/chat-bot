"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { UPLOAD_URL } from "@/lib/urls";

export function FileUploadArea() {
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);

  const uploadFile = useCallback(
    async (file: File) => {
      setError(null);
      setStatus("uploading");
      setFileName(file.name);
      const formData = new FormData();
      formData.set("file", file);

      try {
        const res = await fetch(UPLOAD_URL, {
          method: "POST",
          body: formData,
        });
        const data = (await res.json().catch(() => ({}))) as {
          ok?: boolean;
          docId?: string;
          fileName?: string;
          error?: string;
        };

        if (!res.ok) {
          throw new Error(
            typeof data.error === "string" ? data.error : "Upload failed",
          );
        }
        if (!data.ok || !data.fileName || !data.docId) {
          throw new Error(data.error || "Upload failed");
        }

        if (typeof window !== "undefined") {
          sessionStorage.setItem("lastUploadedFile", data.fileName);
          sessionStorage.setItem("lastUploadedDocId", data.docId);
        }
        router.push(
          `/chat?docId=${encodeURIComponent(data.docId)}&doc=${encodeURIComponent(data.fileName)}`,
        );
      } catch (e) {
        setStatus("error");
        setError(e instanceof Error ? e.message : "Something went wrong");
      }
    },
    [router],
  );

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (file) void uploadFile(file);
    },
    [uploadFile],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files?.[0];
      if (file) void uploadFile(file);
    },
    [uploadFile],
  );

  return (
    <div
      className="mx-auto max-w-lg rounded-2xl border-2 border-dashed border-[var(--border-strong)] bg-[var(--surface)] p-8 shadow-sm transition-colors hover:border-[var(--accent)]/50"
      onDragOver={(e) => e.preventDefault()}
      onDrop={onDrop}
    >
      <div className="flex flex-col items-center text-center">
        <div
          className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--surface-muted)] text-2xl"
          aria-hidden
        >
          📄
        </div>
        <h2 className="text-lg font-semibold text-[var(--text-primary)]">
          Upload a document
        </h2>
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-[var(--text-secondary)]">
          Choose a file to analyze. When the upload finishes, you will be taken
          to the chat to ask questions.
        </p>

        <label
          className={`relative mt-6 inline-flex h-11 min-w-[10rem] cursor-pointer items-center justify-center rounded-full bg-[var(--accent)] text-sm font-semibold text-white shadow-md transition-colors hover:bg-[var(--accent-hover)] has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--accent)] ${
            status === "uploading"
              ? "pointer-events-none opacity-60"
              : ""
          }`}
        >
          <input
            type="file"
            className="absolute inset-0 z-10 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
            onChange={onInputChange}
            disabled={status === "uploading"}
            aria-label={
              status === "uploading"
                ? "Upload in progress"
                : "Choose file to upload"
            }
          />
          <span className="pointer-events-none px-8" aria-hidden>
            {status === "uploading" ? "Uploading…" : "Choose file"}
          </span>
        </label>
        <p className="mt-3 text-xs text-[var(--text-muted)]">
          or drag and drop a file here · max 15 MB
        </p>

        {status === "uploading" && fileName ? (
          <p className="mt-4 truncate text-xs text-[var(--text-secondary)]">
            Sending <span className="font-medium">{fileName}</span>…
          </p>
        ) : null}

        {status === "error" && error ? (
          <p
            className="mt-4 text-sm text-red-600 dark:text-red-400"
            role="alert"
          >
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
