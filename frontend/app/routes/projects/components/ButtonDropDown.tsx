import { useState, useRef, useEffect } from 'react';

interface MenuItem {
  label: string;
  value: string;
  checked?: boolean;
}
interface Props {
  buttonText: string;
  items: MenuItem[];
  onSelect: (item: MenuItem) => void;
}
export default function ButtonDropdown({ buttonText, items, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 shadow-sm hover:bg-gray-50"
      >
        {buttonText} ▾
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-2 w-56 rounded-xl border border-gray-200 bg-white p-2 shadow-lg">
          <ul className="max-h-72 overflow-auto text-sm">
            {items.map((it) => (
              <li key={it.value}>
                <button
                  onClick={() => {
                    onSelect(it);
                  }}
                  className="flex w-full items-center justify-between rounded-lg px-3 py-2 hover:bg-gray-50"
                >
                  <span>{it.label}</span>
                  {it.checked ? <span>✓</span> : null}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
