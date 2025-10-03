type BadgeProps = {
  label: string;
  tone?: "default" | "success" | "warning" | "info";
};

const toneClasses: Record<NonNullable<BadgeProps["tone"]>, string> = {
  default: "bg-slate-800/80 text-slate-200 border-slate-700",
  success: "bg-emerald-500/10 text-emerald-300 border-emerald-500/40",
  warning: "bg-amber-500/10 text-amber-300 border-amber-500/40",
  info: "bg-blue-500/10 text-blue-300 border-blue-500/40",
};

function Badge({ label, tone = "default" }: BadgeProps) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${toneClasses[tone]}`}>
      {label}
    </span>
  );
}

export default Badge;
