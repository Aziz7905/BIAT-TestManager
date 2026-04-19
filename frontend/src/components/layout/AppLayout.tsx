import type { ReactNode } from "react";
import TopNav from "./TopNav";

interface AppLayoutProps {
  children: ReactNode;
  projectName?: string;
}

export default function AppLayout({ children, projectName }: AppLayoutProps) {
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-50">
      <TopNav projectName={projectName} />
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}
