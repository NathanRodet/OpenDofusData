interface Props {
  value: number;
  label: string;
  tone?: "accent" | "ok" | "info";
}

export function ProgressBar({ value, label, tone = "accent" }: Props) {
  return (
    <div className="bar" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
      <i className={tone === "accent" ? undefined : tone} style={{ width: `${value}%` }} />
    </div>
  );
}
