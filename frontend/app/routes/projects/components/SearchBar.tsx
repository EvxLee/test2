import { useId } from 'react';

interface Props {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}
export default function SearchBar({ value, onChange, placeholder }: Props) {
  const id = useId();
  return (
    <label htmlFor={id} className="relative block">
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder ?? 'Search projects...'}
        className="w-full rounded-xl border border-gray-200 bg-white px-3 py-2 pl-9 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
      />
      <span className="pointer-events-none absolute left-3 top-2.5 text-gray-400">
        🔎
      </span>
    </label>
  );
}
