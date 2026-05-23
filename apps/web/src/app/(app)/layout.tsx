import type { ReactNode } from "react";

import { Header } from "@/components/header";
import { Sidebar } from "@/components/sidebar";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <Header />
        <div className="flex-1 p-6">{children}</div>
      </div>
    </div>
  );
}
