import type { ReactNode } from "react";

export interface IconProps {
  size?: number;
  className?: string;
}

interface IconShellProps extends IconProps {
  children: ReactNode;
}

function IconShell({ size = 18, className, children }: IconShellProps) {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export function DashboardIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </IconShell>
  );
}

export function FilePlusIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="12" y1="18" x2="12" y2="12" />
      <line x1="9" y1="15" x2="15" y2="15" />
    </IconShell>
  );
}

export function FileTextIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="9" y1="13" x2="15" y2="13" />
      <line x1="9" y1="17" x2="15" y2="17" />
    </IconShell>
  );
}

export function ShieldCheckIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </IconShell>
  );
}

export function UserCheckIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <polyline points="16 11 18 13 22 9" />
    </IconShell>
  );
}

export function ClockIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </IconShell>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
    </IconShell>
  );
}

export function CloseIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </IconShell>
  );
}

export function PlusIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </IconShell>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </IconShell>
  );
}

export function CheckIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M20 6L9 17l-5-5" />
    </IconShell>
  );
}

export function ArrowLeftIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M19 12H5" />
      <path d="M12 19l-7-7 7-7" />
    </IconShell>
  );
}

export function LogInIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" />
      <polyline points="10 17 15 12 10 7" />
      <line x1="15" y1="12" x2="3" y2="12" />
    </IconShell>
  );
}

export function LogOutIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" y1="12" x2="9" y2="12" />
    </IconShell>
  );
}

export function DownloadIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </IconShell>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </IconShell>
  );
}

export function InboxIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
      <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
    </IconShell>
  );
}

export function InfoIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </IconShell>
  );
}

export function LayersIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </IconShell>
  );
}

export function CheckCircleIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M8.5 12.2l2.3 2.3 4.7-4.9" />
    </IconShell>
  );
}

export function AlertTriangleIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <path d="M12 3.5l9.5 16.5H2.5z" />
      <line x1="12" y1="9.5" x2="12" y2="13.5" />
      <line x1="12" y1="16.7" x2="12" y2="16.71" />
    </IconShell>
  );
}

export function XCircleIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="12" cy="12" r="9" />
      <line x1="9.3" y1="9.3" x2="14.7" y2="14.7" />
      <line x1="14.7" y1="9.3" x2="9.3" y2="14.7" />
    </IconShell>
  );
}

export function MinusCircleIcon(props: IconProps) {
  return (
    <IconShell {...props}>
      <circle cx="12" cy="12" r="9" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </IconShell>
  );
}
