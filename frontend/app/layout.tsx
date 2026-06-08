import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Aleks — Chat with Aleks Gornik's Brain",
  description:
    "Ask any question about breaking into tech, data science, internships, or engineering school. Powered by every video Aleks has ever made.",
  openGraph: {
    title: "AI Aleks",
    description: "Chat with an AI trained on every Aleks Gornik YouTube video.",
    siteName: "AI Aleks",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable} dark`} suppressHydrationWarning>
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
