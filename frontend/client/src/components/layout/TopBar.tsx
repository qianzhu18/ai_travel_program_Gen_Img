import { ReactNode } from "react";

interface TopBarProps {
  title: string;
  children?: ReactNode;
}

export default function TopBar({ title, children }: TopBarProps) {
  return (
    <header className="h-[60px] bg-white border-b border-border flex items-center justify-between px-6 shrink-0">
      <h1 className="text-xl font-semibold text-foreground">{title}</h1>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </header>
  );
}
