import { ReactNode } from "react";
import Sidebar from "./Sidebar";
import TopBar from "./TopBar";

interface MainLayoutProps {
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export default function MainLayout({ title, children, actions }: MainLayoutProps) {
  return (
    <div className="flex h-screen bg-background overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar title={title}>{actions}</TopBar>
        <main className="flex-1 overflow-auto p-6 custom-scrollbar">
          {children}
        </main>
      </div>
    </div>
  );
}
