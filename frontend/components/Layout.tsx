"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Home, FileVideo, Library, Award, History, Settings } from "lucide-react"
import { cn } from "@/lib/utils"

const navItems = [
  { href: "/", label: "ホーム", icon: Home },
  { href: "/upload", label: "新規解析", icon: FileVideo },
  { href: "/library", label: "ライブラリ", icon: Library },
  { href: "/scoring", label: "採点モード", icon: Award },
  { href: "/history", label: "履歴", icon: History },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-brand" aria-label="AI手技モーション伝承ライブラリ">
            <span className="app-brand__symbol">AI</span>
            <div className="app-brand__copy">
              <span className="app-brand__title">AI手技モーション伝承ライブラリ</span>
              <span className="app-brand__subtitle">Surgical Motion Intelligence Hub</span>
            </div>
          </div>
          <button className="app-settings-button" type="button" aria-label="設定">
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </header>

      <div className="app-layout">
        <aside className="app-sidebar">
          <nav className="app-sidebar__nav">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive =
                pathname === item.href || (item.href !== "/" && pathname?.startsWith(item.href))

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn("app-nav-link", isActive && "app-nav-link--active")}
                >
                  <Icon className="app-nav-link__icon" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
        </aside>

        <main className="app-main">{children}</main>
      </div>
    </div>
  )
}
