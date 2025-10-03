import Link from "next/link";
import { readSite } from "@/lib/site";
import SearchBox from "@/components/SearchBox";
import { DEFAULT_PHONE } from "@/lib/data";

export default async function Header() {
  const site = await readSite();
  return (
    <header className="sticky top-0 z-50 border-b bg-black/70 backdrop-blur">
      <div className="container-base h-16 flex items-center justify-between gap-4 text-white">
        <div className="hidden md:block w-[340px]">
          <SearchBox />
        </div>
        <Link href="/" className="flex items-center gap-3">
          <img src={site.brand.logo} alt={site.brand.name} className="h-9 w-auto" />
          <span className="text-xl font-semibold tracking-wide">{site.brand.name}</span>
        </Link>
        <nav className="hidden md:flex items-center gap-6 text-sm">
          <Link href="/" className="hover:text-gray-300">Inicio</Link>
          <a
            href={`https://wa.me/${DEFAULT_PHONE}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-gray-300"
          >
            Contacto
          </a>
        </nav>
      </div>
    </header>
  );
}
