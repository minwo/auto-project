import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "국내주식 후보 분석",
  description: "국내주식 후보 점수와 리스크를 확인하는 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
