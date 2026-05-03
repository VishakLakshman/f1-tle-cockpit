import type { Metadata } from "next";
import "./globals.css"
import Sidebar from "@/components/Sidebar";
import GlobalHeader from "@/components/GlobalHeader";

export const metadata: Metadata = {
  title: "F1 TLE",
  description: "F1 Telemetry Dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <div className="main-area">
            <GlobalHeader />
            <main className="main-content">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}