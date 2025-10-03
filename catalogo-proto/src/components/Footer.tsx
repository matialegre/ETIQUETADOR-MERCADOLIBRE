import { readSite } from "@/lib/site";
import Link from "next/link";

export default async function Footer() {
  const site = await readSite();
  return (
    <footer className="mt-10 border-t bg-black/80 text-white">
      <div className="container-base py-8 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <img src={site.brand.logo} alt={site.brand.name} className="h-7 w-auto" />
          <span className="text-sm text-gray-300">© {new Date().getFullYear()} {site.brand.name}</span>
        </div>
        {site.social?.instagram && (
          <Link href={site.social.instagram} target="_blank" className="text-sm hover:text-gray-300">
            Instagram
          </Link>
        )}
      </div>
    </footer>
  );
}
