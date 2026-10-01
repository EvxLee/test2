import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

interface ChatContextType {
  context: any;
  setContext: (context: any) => void;
}

const ChatContext = createContext<ChatContextType | null>(null);

export function ChatContextProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState(null);
  return (
    <ChatContext.Provider value={{ context, setContext }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within ChatContextProvider');
  return ctx;
}
