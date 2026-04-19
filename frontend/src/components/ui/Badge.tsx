type BadgeColor = "blue" | "green" | "red" | "yellow" | "orange" | "slate" | "purple";

const colorClasses: Record<BadgeColor, string> = {
  blue: "bg-blue-100 text-blue-700",
  green: "bg-green-100 text-green-700",
  red: "bg-red-100 text-red-700",
  yellow: "bg-yellow-100 text-yellow-700",
  orange: "bg-orange-100 text-orange-700",
  slate: "bg-slate-100 text-slate-600",
  purple: "bg-purple-100 text-purple-700",
};

interface BadgeProps {
  label: string;
  color?: BadgeColor;
  dot?: boolean;
}

export default function Badge({ label, color = "slate", dot = false }: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium",
        colorClasses[color],
      ].join(" ")}
    >
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current" />}
      {label}
    </span>
  );
}
