import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import dayjs from "dayjs";
import localeEs from "dayjs/locale/es";
import localizedFormat from "dayjs/plugin/localizedFormat";
import relativeTime from "dayjs/plugin/relativeTime";

import Badge from "../components/Badge";
import Table from "../components/Table";
import { api } from "../lib/api";
import type { Campaign } from "../types";

dayjs.locale(localeEs);
dayjs.extend(relativeTime);
dayjs.extend(localizedFormat);

const channelTone: Record<string, "info" | "warning" | "success"> = {
  email: "info",
  whatsapp: "success",
  social: "warning",
};

const statusTone: Record<string, "default" | "success" | "warning"> = {
  active: "success",
  draft: "default",
  paused: "warning",
};

const columns: ColumnDef<Campaign>[] = [
  {
    header: "Campaña",
    accessorKey: "name",
    cell: (info) => (
      <div className="space-y-1">
        <p className="font-medium text-white">{info.getValue<string>()}</p>
        <p className="text-xs text-slate-400">
          {info.row.original.notes ?? "Sin notas"}
        </p>
      </div>
    ),
  },
  {
    header: "Canal",
    accessorKey: "channel",
    cell: (info) => (
      <Badge
        label={info.getValue<string>().toUpperCase()}
        tone={channelTone[info.getValue<string>()] ?? "default"}
      />
    ),
  },
  {
    header: "Estado",
    accessorKey: "status",
    cell: (info) => (
      <Badge
        label={info.getValue<string>().toUpperCase()}
        tone={statusTone[info.getValue<string>()] ?? "default"}
      />
    ),
  },
  {
    header: "Programado",
    accessorKey: "scheduled_at",
    cell: (info) =>
      info.getValue<string>()
        ? `${dayjs(info.getValue<string>()).format("LLL")} (${dayjs(info.getValue<string>()).fromNow()})`
        : "Sin fecha",
  },
  {
    header: "Presupuesto",
    accessorKey: "budget",
    cell: (info) =>
      info.getValue<number | null>() ? `$${info.getValue<number>()} USD` : "N/A",
  },
];

function CampaignsPage() {
  const { data, isLoading, error } = useQuery<Campaign[]>({
    queryKey: ["campaigns"],
    queryFn: async () => {
      const response = await api.get<Campaign[]>("/campaigns/");
      return response.data;
    },
  });

  if (isLoading) {
    return <p className="text-sm text-slate-400">Cargando campañas...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-400">No se pudieron cargar las campañas.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h3 className="text-xl font-semibold text-white">Campañas</h3>
        <p className="text-sm text-slate-400">
          Visión general de campañas de marketing y su estado operativo.
        </p>
      </header>
      <Table<Campaign>
        data={data ?? []}
        columns={columns}
        empty="No hay campañas configuradas"
      />
    </div>
  );
}

export default CampaignsPage;
