import { useState, useRef, useEffect } from "react";
import type { AdminUser } from "../../types/accounts";

interface UserPickerProps {
  users: AdminUser[];
  value: number | null;
  onChange: (userId: number | null) => void;
  placeholder?: string;
  disabled?: boolean;
}

export default function UserPicker({
  users,
  value,
  onChange,
  placeholder = "Search user…",
  disabled = false,
}: UserPickerProps) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const selected = value !== null ? users.find((u) => u.id === value) ?? null : null;

  const filtered = query.trim()
    ? users.filter((u) => {
        const name = `${u.first_name} ${u.last_name}`.toLowerCase();
        return name.includes(query.toLowerCase()) || u.email.toLowerCase().includes(query.toLowerCase());
      })
    : users;

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  function handleSelect(user: AdminUser) {
    onChange(user.id);
    setQuery("");
    setOpen(false);
  }

  function handleClear() {
    onChange(null);
    setQuery("");
  }

  return (
    <div ref={containerRef} className="relative">
      <div
        className={`flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm ${
          disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"
        }`}
        onClick={() => !disabled && setOpen(true)}
      >
        {selected ? (
          <>
            <span className="flex-1 truncate text-slate-900">
              {selected.first_name} {selected.last_name}
              <span className="ml-2 text-slate-400 text-xs">{selected.email}</span>
            </span>
            {!disabled && (
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); handleClear(); }}
                className="text-slate-400 hover:text-slate-600"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </>
        ) : (
          <span className="text-slate-400">{placeholder}</span>
        )}
      </div>

      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="p-2 border-b border-slate-100">
            <input
              autoFocus
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type to filter…"
              className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-blue-400"
            />
          </div>
          <ul className="max-h-52 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-400">No users found</li>
            ) : (
              filtered.map((u) => (
                <li
                  key={u.id}
                  onClick={() => handleSelect(u)}
                  className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-slate-50"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700 shrink-0">
                    {u.first_name[0]}{u.last_name[0]}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium text-slate-900">
                      {u.first_name} {u.last_name}
                    </p>
                    <p className="truncate text-xs text-slate-400">{u.email}</p>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}
