import type { ReactNode } from "react";
import { ProgressBar } from "./ProgressBar";

interface Props {
  title: string;
  big: string;
  unit: string;
  progress: number;
  label: string;
  tone?: "accent" | "ok" | "info";
  facts: ReactNode;
}

export function StatCard({ title, big, unit, progress, label, tone, facts }: Props) {
  return (
    <div className="stat">
      <h3>{title}</h3>
      <div className="big">{big}<small>{unit}</small></div>
      <ProgressBar value={progress} label={label} tone={tone} />
      <div className="sub facts">{facts}</div>
    </div>
  );
}
