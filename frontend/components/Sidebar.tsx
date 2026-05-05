"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const NAV = [
  { href: "/qualifying", label: "Qualifying Ghost", icon: "/icons/ghost.png" },
  { href: "/tyres", label: "Tyre Degradation", icon: "/icons/tyre.png" },
  { href: "/strategy", label: "Race Strategy", icon: "/icons/tyre-strategy.png" },
];

export default function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sidebar">
      <div className="sidebar-logo"><img src="/icons/f1-logo.png" alt="" style={{ width: "35px", height: "35px" }}/></div>
      <nav className="sidebar-nav">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            title={n.label}
            className={clsx("sidebar-item", path === n.href && "active")}
          >
            <span className="sidebar-icon">
          {n.icon && (
            <img src={n.icon} alt="" style={{ width: "25px", height: "25px" }}/>
          )}</span>
          </Link>
        ))}
      </nav>
    </aside>
  );
}