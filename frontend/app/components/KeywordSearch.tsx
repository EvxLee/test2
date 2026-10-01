import React, { useState } from "react";

interface KeywordSearchProps {
  keywords: string[];
  onKeywordsChange: (keywords: string[]) => void;
  placeholder?: string;
}

export default function KeywordSearch({
  keywords,
  onKeywordsChange,
  placeholder = "Type a keyword and press Enter…",
}: KeywordSearchProps) {
  const [input, setInput] = useState("");

  const addKeyword = () => {
    const trimmed = input.trim().toLowerCase();
    if (trimmed && !keywords.includes(trimmed)) {
      onKeywordsChange([...keywords, trimmed]);
    }
    setInput("");
  };

  const removeKeyword = (kw: string) => {
    onKeywordsChange(keywords.filter((k) => k !== kw));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addKeyword();
    } else if (e.key === "Backspace" && input === "" && keywords.length > 0) {
      removeKeyword(keywords[keywords.length - 1]);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5 bg-white rounded-lg border border-gray-200 px-4 py-2 w-full min-h-[42px] cursor-text">
      {/* Tag icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-4 h-4 text-gray-400 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M7 7h.01M7 3H5a2 2 0 0 0-2 2v2a2 2 0 0 0 .586 1.414l9 9a2 2 0 0 0 2.828 0l4-4a2 2 0 0 0 0-2.828l-9-9A2 2 0 0 0 7 3z"
        />
      </svg>

      {/* Active keyword tags */}
      {keywords.map((kw) => (
        <span
          key={kw}
          className="inline-flex items-center gap-1 bg-[#8B1E2F]/10 text-[#8B1E2F] text-xs font-semibold px-2.5 py-1 rounded-full select-none"
        >
          {kw}
          <button
            type="button"
            onClick={() => removeKeyword(kw)}
            className="ml-0.5 rounded-full hover:bg-[#8B1E2F]/20 transition-colors p-0.5"
            aria-label={`Remove keyword "${kw}"`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-3 h-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2.5}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </span>
      ))}

      {/* Text input */}
      <input
        type="text"
        placeholder={keywords.length === 0 ? placeholder : "Add another…"}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        className="flex-grow bg-transparent outline-none text-gray-600 placeholder-gray-400 text-sm min-w-[160px]"
      />

      {/* Add button — only visible while typing */}
      {input.trim() && (
        <button
          type="button"
          onClick={addKeyword}
          className="shrink-0 text-[#8B1E2F] hover:text-[#5a1320] transition-colors"
          aria-label="Add keyword"
          title="Add keyword (or press Enter)"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
        </button>
      )}

      {/* Clear all — only when tags exist and not typing */}
      {keywords.length > 1 && !input.trim() && (
        <button
          type="button"
          onClick={() => onKeywordsChange([])}
          className="shrink-0 text-xs text-gray-400 hover:text-gray-600 transition-colors ml-1"
          aria-label="Clear all keywords"
          title="Clear all keywords"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
