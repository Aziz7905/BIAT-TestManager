import { useEffect, useRef, useState, type ReactNode } from "react";
import { DotsIcon, PlusIcon } from "./TreeIcons";

interface NodeActionMenuItem {
  label: string;
  onSelect: () => void;
  icon?: ReactNode;
  tone?: "default" | "danger";
}

interface NodeActionMenuProps {
  items: NodeActionMenuItem[];
  title: string;
  variant?: "menu" | "plus";
  align?: "left" | "right";
}

export default function NodeActionMenu({
  items,
  title,
  variant = "menu",
  align = "right",
}: NodeActionMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    function handlePointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  return (
    <div ref={containerRef} className="relative shrink-0">
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        title={title}
        className={`rounded-md p-1 text-slate-400 transition ${
          variant === "plus"
            ? "hover:bg-blue-50 hover:text-blue-600"
            : "hover:bg-slate-200 hover:text-slate-700"
        }`}
      >
        {variant === "plus" ? <PlusIcon /> : <DotsIcon />}
      </button>

      {open && (
        <div
          className={`absolute top-full z-20 mt-1 min-w-40 rounded-md border border-slate-200 bg-white py-1 shadow-lg ${
            align === "left" ? "left-0" : "right-0"
          }`}
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setOpen(false);
                item.onSelect();
              }}
              className={`flex w-full items-center gap-2 px-3 py-2 text-left text-xs transition ${
                item.tone === "danger"
                  ? "text-red-600 hover:bg-red-50"
                  : "text-slate-700 hover:bg-slate-50"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
