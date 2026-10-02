import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { LearningProvider } from "@/store/LearningContext";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-geist-sans",
});

export const metadata: Metadata = {
  title: "Adaptive Learning Engine",
  description: "Structured adaptive lessons and practice",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="font-sans">
        <LearningProvider>{children}</LearningProvider>
      </body>
    </html>
  );
}
