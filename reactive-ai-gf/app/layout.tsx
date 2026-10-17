import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Claudina",
  description: "A private chat with Claudina",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}