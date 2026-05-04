import { Suspense } from "react";
import { ChatClient } from "@/components/ChatClient";

function ChatFallback() {
  return (
    <div className="flex min-h-[100dvh] items-center justify-center bg-[var(--page-bg)] text-sm text-[var(--text-muted)]">
      Loading chat…
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<ChatFallback />}>
      <ChatClient />
    </Suspense>
  );
}
