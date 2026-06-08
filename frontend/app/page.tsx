"use client";

import { useState } from "react";
import { GatePage } from "@/components/gate-page";
import { ChatPage } from "@/components/chat-page";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [userName, setUserName] = useState<string>("");

  if (token) {
    return <ChatPage token={token} userName={userName} />;
  }

  return (
    <GatePage
      onSuccess={(t, name) => {
        setToken(t);
        setUserName(name);
      }}
    />
  );
}
