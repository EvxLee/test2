import { useState } from "react";
import { Search, X } from "lucide-react";
import ReactMarkdown from 'react-markdown';

interface ChatbotProps {
  context?: {
    type: 'projects' | 'general';
    data?: any;
  };
}

export default function Chatbot({ context }: ChatbotProps = {}) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<
    { sender: "user" | "ai"; text: string }[]
  >([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);

  const BASE_URL = import.meta.env.VITE_ATLAS_API_URL;
  const API_TOKEN = import.meta.env.VITE_ATLAS_API_TOKEN;

  const buildContextString = (userQuestion: string) => {
    if (context?.type === 'projects' && context.data) {
      const { filteredProjects, selectedProject, filters } = context.data;
      let ctx = "Context: You are analyzing internal projects.\n\n";

      if (selectedProject) {
        ctx += `Currently viewing project: ${selectedProject.name}\n`;
        ctx += `- Company: ${selectedProject.startupName}\n`;
        ctx += `- Vertical: ${selectedProject.vertical}\n`;
        ctx += `- Stage: ${selectedProject.status}\n`;
        ctx += `- Owner: ${selectedProject.owner}\n\n`;
      }

      if (filters && Object.keys(filters).length > 0) {
        ctx += `Active filters: ${JSON.stringify(filters)}\n`;
      }

      ctx += `Total filtered projects: ${filteredProjects?.length || 0}\n`;

      if (filteredProjects?.length > 0 && filteredProjects.length <= 30) {
        ctx += `Projects in view: ${filteredProjects.map((p: { name: string }) => p.name).join(', ')}\n`;
      }

      return `${ctx}\nUser question: ${userQuestion}`;
    }
    return userQuestion;
  };

  const handleSend = async (text: string) => {
    if (!text.trim()) return;

    const userMsg = { sender: "user" as const, text };
    setMessages((prev) => [...prev, userMsg]);
    setQuery("");
    setIsLoading(true);

    try {
      // Build context-aware message
      const fullMessage = buildContextString(text);

      // Build request payload, only including optional fields if they have values
      const payload: any = {
        message: fullMessage,
      };

      if (threadId) {
        payload.thread_id = threadId;
      }

      if (messages.length > 0) {
        payload.conversation_history = messages.map(m => ({
          role: m.sender === 'user' ? 'user' : 'assistant',
          content: m.text
        }));
      }

      const response = await fetch(`${BASE_URL.replace(/\/$/, '')}/atlas/chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${API_TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error('API error response:', errorText);
        throw new Error(`API request failed: ${response.status} ${errorText}`);
      }

      const data = await response.json();

      setThreadId(data.thread_id);

      setMessages((prev) => [...prev, {
        sender: "ai",
        text: data.response || "I couldn't generate a response."
      }]);
    } catch (error) {
      console.error('Chat error:', error);
      setMessages((prev) => [...prev, {
        sender: "ai",
        text: "Sorry, I encountered an error. Please try again."
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Send on Enter key
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(query);
    }
  };

  return (
    <div>
      <button
        onClick={() => {setIsOpen(!isOpen); setMessages([]); setThreadId(null);} }
        className="fixed bottom-4 right-4 bg-red-600 text-white p-3 rounded-full shadow-lg hover:bg-red-700 z-50 transition"
      >
        <Search />
      </button>

      {isOpen && (
        <div
          className="fixed bottom-4 right-4 w-[480px] h-[80vh] bg-white border border-gray-300 
                     rounded-3xl shadow-2xl flex flex-col z-50 overflow-hidden transition-all duration-300"
        >
          <div className="p-4 border-b flex justify-between items-center bg-white/90 backdrop-blur-sm">
            <h2 className="text-lg font-semibold text-gray-800">Ask AI</h2>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-500 hover:text-gray-700"
            >
              <X size={18} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.length === 0 ? (
              <p className="text-gray-500 text-sm leading-relaxed">
                If you ask any questions related to ongoing projects, I'll provide
                answers using external data sources.
              </p>
            ) : (
              messages.map((msg, i) => (
                <div
                  key={i}
                  className={`max-w-[85%] px-3 py-2 rounded-xl text-sm ${
                    msg.sender === "user"
                      ? "bg-red-600 text-white self-end ml-auto"
                      : "bg-gray-200 text-gray-800"
                  }`}
                >
                  {msg.sender === "ai" ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc ml-4 mb-2 last:mb-0">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 last:mb-0">{children}</ol>,
                        li: ({ children }) => <li className="mb-1">{children}</li>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        em: ({ children }) => <em className="italic">{children}</em>,
                        code: ({ children }) => <code className="bg-gray-300 px-1 rounded text-xs">{children}</code>,
                      }}
                    >
                      {msg.text}
                    </ReactMarkdown>
                  ) : (
                    msg.text
                  )}
                </div>
              ))
            )}
            {isLoading && (
              <div className="max-w-[85%] px-3 py-2 rounded-xl text-sm bg-gray-200 text-gray-800">
                <span className="animate-pulse">Thinking...</span>
              </div>
            )}
          </div>

          <div className="border-t bg-white p-4">
            <textarea
              className="w-full border rounded-xl p-3 text-sm resize-none focus:outline-none
                         focus:ring-2 focus:ring-red-500 placeholder:text-gray-400"
              rows={2}
              placeholder="Type a message and press Enter..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
          </div>
        </div>
      )}
    </div>
  );
}
