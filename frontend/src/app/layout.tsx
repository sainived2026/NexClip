import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "NexClip — Turn Long Videos Into Viral Clips in Seconds",
  description:
    "AI-powered video clipping agent that transforms long-form content into viral short-form clips for TikTok, YouTube Shorts, and Instagram Reels.",
  keywords: ["AI", "video clipping", "viral clips", "short-form content", "TikTok", "YouTube Shorts"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
