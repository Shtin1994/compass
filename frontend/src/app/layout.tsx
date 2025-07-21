import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { buttonVariants } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { LayoutDashboard, Cable, Database, Lightbulb, Settings } from "lucide-react";
import { Providers } from "./providers"; // Мы создадим этот файл

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Insight Compass",
  description: "Your AI-powered Telegram analyst",
};

// Навигационные ссылки
const navLinks = [
  { href: "/channels", label: "Каналы", icon: Cable },
  { href: "/dashboards", label: "Дашборды", icon: LayoutDashboard },
  { href: "/data", label: "Данные", icon: Database },
  { href: "/insights", label: "Инсайты", icon: Lightbulb },
  { href: "/settings", label: "Настройка", icon: Settings },
];

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" style={{ colorScheme: "dark" }}>
      <body className={cn("min-h-screen bg-background font-sans antialiased", inter.className)}>
        <Providers> {/* Оборачиваем все в провайдеры */}
          <div className="relative flex min-h-screen flex-col">
            <div className="flex-1">
              <div className="border-b">
                <div className="flex h-16 items-center px-4 sm:px-6 lg:px-8">
                  <h1 className="text-xl font-bold tracking-tight">Инсайт-Компас</h1>
                  <nav className="mx-auto flex items-center space-x-2 lg:space-x-4">
                    {navLinks.map((link) => (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={cn(
                          buttonVariants({ variant: "ghost" }),
                          "text-sm font-medium transition-colors hover:text-primary"
                        )}
                      >
                        <link.icon className="mr-2 h-4 w-4" />
                        {link.label}
                      </Link>
                    ))}
                  </nav>
                </div>
              </div>
              <main className="flex-1 p-4 sm:p-6 lg:p-8">
                {children}
              </main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}