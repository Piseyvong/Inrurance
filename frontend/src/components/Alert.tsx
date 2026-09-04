import type { ReactNode } from "react";

interface AlertProps {
  tone?: "info" | "warning" | "danger" | "success";
  children: ReactNode;
}

export function Alert({ tone = "info", children }: AlertProps) {
  return <div className={`alert ${tone}`}>{children}</div>;
}
