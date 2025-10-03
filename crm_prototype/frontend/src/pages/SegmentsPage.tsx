import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";

import Table from "../components/Table";
import { api } from "../lib/api";
import type { Segment } from "../types";

const columns: ColumnDef<Segment>[] = [
  {
    header: "Nombre",
    accessorKey: "name",
    cell: (info) => (
      <div className="space-y-1">
        <p className="font-medium text-white">{info.getValue<string>()}</p>
        <p className="text-xs text-slate-400">
          {info.row.original.criteria ?? "Sin criterio definido"}
        </p>
      </div>
    ),
  },
  {
    header: "Descripción",
    accessorKey: "description",
    cell: (info) => info.getValue<string>() ?? "—",
  },
];

function SegmentsPage() {
  const { data, isLoading, error } = useQuery<Segment[]>({
    queryKey: ["segments"],
    queryFn: async () => {
      const response = await api.get<Segment[]>("/segments/");
      return response.data;
    },
  });

  if (isLoading) {
    return <p className="text-sm text-slate-400">Cargando segmentos...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-400">No se pudieron cargar los segmentos.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h3 className="text-xl font-semibold text-white">Segmentos</h3>
        <p className="text-sm text-slate-400">
          Agrupaciones de clientes basadas en comportamiento y preferencias.
        </p>
      </header>
      <Table<Segment> data={data ?? []} columns={columns} empty="Sin segmentos" />
    </div>
  );
}

export default SegmentsPage;
