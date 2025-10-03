import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { readSite } from "@/lib/site";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  try {
    const site = await readSite();
    const title = site?.brand?.name || "Avanti Indumentaria";
    return {
      title,
      description: `${title} - Catálogo de productos`,
    };
  } catch {
    return {
      title: "Avanti Indumentaria",
      description: "Catálogo de productos",
    };
  }
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <Header />
        <main className="container-base py-6">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
