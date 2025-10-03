import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";

import Badge from "../components/Badge";
import Table from "../components/Table";
import { api } from "../lib/api";
import type { Customer } from "../types";

const columns: ColumnDef<Customer>[] = [
  {
    header: "Nombre",
    accessorKey: "full_name",
    cell: (info) => (
      <div className="space-y-1">
        <p className="font-medium text-white">{info.getValue<string>()}</p>
        <p className="text-xs text-slate-400">{info.row.original.email}</p>
      </div>
    ),
  },
  {
    header: "Canal origen",
    accessorKey: "source",
    cell: (info) => info.getValue<string>() ?? "—",
  },
  {
    header: "Preferencias",
    accessorKey: "preferences",
    cell: (info) => info.getValue<string>() || "No definido",
  },
  {
    header: "Segmentos",
    accessorFn: (row) => row.segments,
    cell: (info) => (
      <div className="flex flex-wrap gap-2">
        {info.getValue<any[]>().map((segment) => (
          <Badge key={segment.id} label={segment.name} tone="info" />
        ))}
      </div>
    ),
  },
  {
    header: "VIP",
    accessorKey: "is_vip",
    cell: (info) =>
      info.getValue<boolean>() ? (
        <Badge label="VIP" tone="success" />
      ) : (
        <span className="text-xs text-slate-500">No</span>
      ),
  },
];

function CustomersPage() {
  const { data, isLoading, error } = useQuery<Customer[]>({
    queryKey: ["customers"],
    queryFn: async () => {
      const response = await api.get<Customer[]>("/customers/");
      return response.data;
    },
  });

  if (isLoading) {
    return <p className="text-sm text-slate-400">Cargando clientes...</p>;
  }

  if (error) {
    return <p className="text-sm text-red-400">No se pudieron cargar los clientes.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <h3 className="text-xl font-semibold text-white">Clientes</h3>
        <p className="text-sm text-slate-400">
          Lista de clientes centralizados con segmentación y preferencias básicas.
        </p>
      </header>
      <Table<Customer> data={data ?? []} columns={columns} empty="Sin clientes registrados" />
    </div>
  );
}

export default CustomersPage;
