import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import Layout from "@/components/Layout";
import EnvironmentBadge from "@/components/EnvironmentBadge";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "MindモーションAI",
  description: "手術手技をデータ化し、指導医の技術を学生・研修医に効果的に伝承するWebアプリケーション",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className={inter.className}>
        <EnvironmentBadge />
        <Layout>{children}</Layout>
      </body>
    </html>
  );
}
