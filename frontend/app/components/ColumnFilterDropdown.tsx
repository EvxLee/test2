import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

export interface ColumnFilterOption {
  value: string;
  label: string;
  group?: string;
  subgroup?: string;
  searchText?: string;
}

interface ColumnFilterDropdownProps {
  label: string;
  options: ColumnFilterOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  searchable?: boolean;
  placeholder?: string;
  widthClassName?: string;
}

export default function ColumnFilterDropdown({
  label,
  options,
  selected,
  onChange,
  searchable = false,
  placeholder = "Search...",
  widthClassName = "w-64",
}: ColumnFilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [panelStyle, setPanelStyle] = useState<{ top: number; left: number }>({
    top: 0,
    left: 0,
  });

  useEffect(() => {
    function updatePanelPosition() {
      if (!isOpen || !buttonRef.current) return;

      const rect = buttonRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const estimatedWidth = widthClassName === "w-80" ? 320 : 256;
      const left = Math.min(
        Math.max(12, rect.left),
        Math.max(12, viewportWidth - estimatedWidth - 12)
      );

      setPanelStyle({
        top: rect.bottom + 8,
        left,
      });
    }

    updatePanelPosition();

    window.addEventListener("resize", updatePanelPosition);
    window.addEventListener("scroll", updatePanelPosition, true);
    return () => {
      window.removeEventListener("resize", updatePanelPosition);
      window.removeEventListener("scroll", updatePanelPosition, true);
    };
  }, [isOpen, widthClassName]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      const clickedTrigger = rootRef.current?.contains(target);
      const clickedPanel = panelRef.current?.contains(target);

      if (!clickedTrigger && !clickedPanel) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const filteredOptions = useMemo(() => {
    const search = query.toLowerCase().trim();
    if (!search) return options;

    return options.filter((option) => {
      const haystack = [
        option.label,
        option.group || "",
        option.subgroup || "",
        option.searchText || "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(search);
    });
  }, [options, query]);

  const groupedOptions = useMemo(() => {
    const groups = new Map<string, Map<string, ColumnFilterOption[]>>();

    filteredOptions.forEach((option) => {
      const group = option.group || "";
      const subgroup = option.subgroup || "";

      if (!groups.has(group)) groups.set(group, new Map());
      const subgroups = groups.get(group)!;
      if (!subgroups.has(subgroup)) subgroups.set(subgroup, []);
      subgroups.get(subgroup)!.push(option);
    });

    return Array.from(groups.entries());
  }, [filteredOptions]);

  function toggleValue(value: string) {
    if (selected.includes(value)) {
      onChange(selected.filter((item) => item !== value));
      return;
    }
    onChange([...selected, value]);
  }

  return (
    <div ref={rootRef} className="relative" onClick={(event) => event.stopPropagation()}>
      <button
        ref={buttonRef}
        type="button"
        className={`mt-1 inline-flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
          selected.length
            ? "border-rose-300 bg-rose-50 text-[#8B1E2F]"
            : "border-gray-200 bg-white text-gray-500"
        }`}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span>{label}</span>
        {selected.length > 0 && <span>({selected.length})</span>}
      </button>

      {isOpen && (
        createPortal(
          <div
            ref={panelRef}
            className={`fixed z-[100] flex max-h-96 flex-col rounded-xl border border-gray-200 bg-white p-3 shadow-xl ${widthClassName}`}
            style={panelStyle}
          >
            {searchable && (
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder={placeholder}
                className="mb-3 w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-700 outline-none focus:border-rose-300"
              />
            )}

            <div className="min-h-0 flex-1 overflow-y-auto pr-1">
              {groupedOptions.length === 0 ? (
                <div className="py-3 text-sm text-gray-500">No matches</div>
              ) : (
                groupedOptions.map(([group, subgroups]) => (
                  <div key={group || "default"} className="mb-3 last:mb-0">
                    {group && (
                      <div className="mb-1 text-[11px] font-bold uppercase tracking-wide text-gray-500">
                        {group}
                      </div>
                    )}

                    {Array.from(subgroups.entries()).map(([subgroup, subgroupOptions]) => (
                      <div key={`${group}-${subgroup || "default"}`} className="mb-2 last:mb-0">
                        {subgroup && (
                          <div className="mb-1 pl-1 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                            {subgroup}
                          </div>
                        )}

                        <div className="space-y-1">
                          {subgroupOptions.map((option) => (
                            <label
                              key={option.value}
                              className="flex cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                            >
                              <input
                                type="checkbox"
                                checked={selected.includes(option.value)}
                                onChange={() => toggleValue(option.value)}
                                className="mt-0.5 rounded border-gray-300 text-rose-600 focus:ring-rose-500"
                              />
                              <span>{option.label}</span>
                            </label>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ))
              )}
            </div>

            <div className="mt-3 border-t border-gray-100 pt-3">
              {selected.length > 0 ? (
                <button
                  type="button"
                  className="w-full rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[#8B1E2F]"
                  onClick={() => onChange([])}
                >
                  Clear
                </button>
              ) : (
                <div className="h-2" />
              )}
            </div>
          </div>
          ,
          document.body
        )
      )}
    </div>
  );
}
