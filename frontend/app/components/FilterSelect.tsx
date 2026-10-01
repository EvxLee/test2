import React from "react";

interface FilterSelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  active?: boolean;
}

export default function FilterSelect({
  active,
  children,
  className,
  ...props
}: FilterSelectProps) {
  return (
    <div className="relative inline-flex items-center">
      <select
        {...props}
        className={`
          appearance-none rounded-lg pl-3 pr-7 py-1.5 text-sm cursor-pointer
          border transition-colors focus:outline-none focus:ring-2 focus:ring-[#8B1E2F] focus:border-[#8B1E2F]
          ${active
            ? "border-[#8B1E2F] text-[#8B1E2F] bg-[#8B1E2F]/5 font-medium"
            : "border-gray-200 text-gray-500 bg-white hover:border-gray-300 hover:text-gray-700"
          }
          ${className || ""}
        `}
      >
        {children}
      </select>
      <svg
        className={`pointer-events-none absolute right-2 w-3 h-3 shrink-0 ${
          active ? "text-[#8B1E2F]" : "text-gray-400"
        }`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2.5}
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    </div>
  );
}
