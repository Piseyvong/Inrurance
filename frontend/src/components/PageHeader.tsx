import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  children?: ReactNode;
}

export function PageHeader({ title, eyebrow, subtitle, children }: PageHeaderProps) {
  return (
    <header className="pageHeader">
      <div>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {subtitle ? <p className="pageSubtitle">{subtitle}</p> : null}
      </div>
      {children ? <div className="pageHeaderActions">{children}</div> : null}
    </header>
  );
}
