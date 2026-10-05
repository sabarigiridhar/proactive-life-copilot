"use client";

import {
  Activity,
  BookOpen,
  Bot,
  ChartNoAxesCombined,
  Home,
  Settings,
  Sparkles,
  WalletCards,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const navigation: Array<{ href: Route; label: string; icon: typeof Home }> = [
  { href: "/", label: "Home", icon: Home },
  { href: "/chat", label: "Copilot", icon: Bot },
  { href: "/wealth", label: "Wealth", icon: WalletCards },
  { href: "/health", label: "Health", icon: Activity },
  { href: "/learning", label: "Learning", icon: BookOpen },
  { href: "/weekly-review", label: "Review", icon: ChartNoAxesCombined },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" href="/" aria-label="Life Copilot home">
          <span className="brand-mark" aria-hidden="true">
            <Sparkles size={18} />
          </span>
          <span>Life Copilot</span>
        </Link>
        <div className="workspace-pill">
          <span aria-hidden="true" /> Local workspace
        </div>
      </header>

      <nav className="primary-nav" aria-label="Primary navigation">
        {navigation.map((item) => {
          const Icon = item.icon;
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className="nav-link"
              aria-current={active ? "page" : undefined}
            >
              <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <main className="main-content">{children}</main>
      <footer className="app-footer">
        <span>Life Copilot</span>
        <span>Your records stay in your configured local data stores.</span>
      </footer>
    </div>
  );
}
