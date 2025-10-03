import { useQuery } from "@tanstack/react-query";

import StatCard from "../components/StatCard";
import { api } from "../lib/api";
import type { DashboardSummary } from "../types";

function DashboardPage() {
  const { data, isLoading, error } = useQuery<DashboardSummary>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const response = await api.get<DashboardSummary>("/dashboard");
      return response.data;
    },
  });

  if (isLoading) {
    return <p className="text-sm text-slate-400">Cargando métricas...</p>;
  }

  if (error) {
    return (
      <p className="text-sm text-red-400">
        No se pudieron cargar los datos del dashboard.
      </p>
    );
  }

  if (!data) {
    return <p className="text-sm text-slate-400">Sin información disponible.</p>;
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Clientes totales" value={data.total_customers} />
        <StatCard label="Clientes VIP" value={data.vip_customers} />
        <StatCard label="Campañas activas" value={data.active_campaigns} />
        <StatCard label="Mensajes pendientes" value={data.queued_messages} />
      </div>
      <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        <h3 className="text-lg font-semibold text-white">Próximos pasos sugeridos</h3>
        <ul className="mt-3 space-y-2 text-sm text-slate-400">
          <li>• Analizá segmentaciones según comportamiento reciente.</li>
          <li>• Validá plantillas pendientes de aprobación antes de enviar.</li>
          <li>• Revisá integraciones para garantizar sincronización de ventas.</li>
        </ul>
      </section>
    </div>
  );
}

export default DashboardPage;
