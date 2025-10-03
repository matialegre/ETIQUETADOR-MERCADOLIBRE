import { NavLink, Outlet } from "react-router-dom";

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/customers", label: "Clientes" },
  { to: "/segments", label: "Segmentos" },
  { to: "/campaigns", label: "Campañas" },
  { to: "/messages", label: "Mensajes" },
  { to: "/integrations", label: "Integraciones" },
];

function Layout() {
  return (
    <div className="min-h-screen flex">
      <aside className="w-60 bg-slate-900 border-r border-slate-800">
        <div className="px-6 py-5 border-b border-slate-800">
          <h1 className="text-xl font-bold tracking-tight">CRM Prototype</h1>
          <p className="text-xs text-slate-400 mt-1">Marketing & Integraciones</p>
        </div>
        <nav className="flex flex-col px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-primary-500 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 bg-slate-950">
        <header className="px-8 py-6 border-b border-slate-800">
          <h2 className="text-2xl font-semibold tracking-tight text-white">
            Panel CRM & Marketing
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Prototipo ejecutable para explorar base funcional.
          </p>
        </header>
        <section className="p-8">
          <Outlet />
        </section>
      </main>
    </div>
  );
}

export default Layout;
