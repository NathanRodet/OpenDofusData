import { CircleAlert, Download, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

type Tone = "warn" | "bad" | "info";

interface Props {
  tone: Tone;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
}

const ICONS = { warn: TriangleAlert, bad: CircleAlert, info: Download } as const;

export function Banner({ tone, title, children, actions }: Props) {
  const Icon = ICONS[tone];
  return (
    <div className={`banner ${tone}`} role={tone === "bad" ? "alert" : "status"}>
      <Icon className="banner-icon" size={20} aria-hidden="true" />
      <div className="banner-body">
        <b>{title}</b>
        {children ? <p>{children}</p> : null}
      </div>
      {actions ? <div className="banner-actions">{actions}</div> : null}
    </div>
  );
}
