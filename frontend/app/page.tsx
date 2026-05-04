import { FileUploadArea } from "@/components/FileUploadArea";

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col bg-[var(--page-bg)]">
      <main className="flex flex-1 flex-col px-4 py-12 sm:px-6 sm:py-16 lg:px-8">
        <div className="mx-auto mb-10 max-w-2xl text-center">
          <p className="mb-2 text-sm font-medium uppercase tracking-wider text-[var(--accent-strong)]">
            Nosh AI
          </p>
          <h1 className="text-balance text-3xl font-bold tracking-tight text-[var(--text-primary)] sm:text-4xl">
            Upload a file, then chat
          </h1>
          <p className="mt-4 text-pretty text-base leading-relaxed text-[var(--text-secondary)] sm:text-lg">
            Upload a document below. After the upload completes, you will be
            redirected to chat where you can send messages and receive replies.
          </p>
        </div>
        <FileUploadArea />
      </main>

      <footer className="mt-auto border-t border-[var(--border)] bg-[var(--surface)] px-4 py-8 sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-center text-sm text-[var(--text-muted)] sm:flex-row sm:text-left">
          <p>© {new Date().getFullYear()} Nosh AI. All rights reserved.</p>
          <nav
            className="flex flex-wrap justify-center gap-x-6 gap-y-2"
            aria-label="Footer"
          >
            <a className="hover:text-[var(--text-primary)]" href="#">
              Help
            </a>
            <a className="hover:text-[var(--text-primary)]" href="#">
              Terms
            </a>
            <a className="hover:text-[var(--text-primary)]" href="#">
              Privacy
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
