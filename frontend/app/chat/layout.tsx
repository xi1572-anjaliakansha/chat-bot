import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Chat — Nosh AI",
  description: "Ask questions about your uploaded document.",
};

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return children;
}
