import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";

import Badge from "../components/Badge";
import Table from "../components/Table";
import { api } from "../lib/api";
import type { InteractionLog, MessageTemplate } from "../types";

const templateColumns: ColumnDef<MessageTemplate>[] = [
  {
    header: "Título",
    accessorKey: "title",
    cell: (info) => (
      <div className="space-y-1">
        <p className="font-medium text-white">{info.getValue<string>()}</p>
        <p className="text-xs text-slate-400">{info.row.original.channel.toUpperCase()}</p>
      </div>
    ),
  },
  {
    header: "Estado",
    accessorKey: "is_approved",
    cell: (info) =>
      info.getValue<boolean>() ? (
        <Badge label="Aprobado" tone="success" />
      ) : (
        <Badge label="Pendiente" tone="warning" />
      ),
  },
  {
    header: "Idioma",
    accessorKey: "language",
    cell: (info) => info.getValue<string>().toUpperCase(),
  },
];

const interactionColumns: ColumnDef<InteractionLog>[] = [
  {
    header: "Cliente",
    accessorKey: "customer_id",
    cell: (info) => `#${info.getValue<number>()}`,
  },
  {
    header: "Canal",
    accessorKey: "channel",
    cell: (info) => info.getValue<string>().toUpperCase(),
  },
  {
    header: "Dirección",
    accessorKey: "direction",
    cell: (info) => (
      <Badge
        label={info.getValue<string>() === "outbound" ? "Saliente" : "Entrante"}
        tone={info.getValue<string>() === "outbound" ? "info" : "success"}
      />
    ),
  },
  {
    header: "Mensaje",
    accessorKey: "message",
    cell: (info) => <p className="text-sm text-slate-300">{info.getValue<string>()}</p>,
  },
  {
    header: "Fecha",
    accessorKey: "occurred_at",
    cell: (info) => new Date(info.getValue<string>()).toLocaleString(),
  },
];

function MessagesPage() {
  const templatesQuery = useQuery<MessageTemplate[]>({
    queryKey: ["message-templates"],
    queryFn: async () => {
      const response = await api.get<MessageTemplate[]>("/messages/templates");
      return response.data;
    },
  });

  const interactionsQuery = useQuery<InteractionLog[]>({
    queryKey: ["interaction-logs"],
    queryFn: async () => {
      const response = await api.get<InteractionLog[]>("/messages/interactions");
      return response.data;
    },
  });

  if (templatesQuery.isLoading || interactionsQuery.isLoading) {
    return <p className="text-sm text-slate-400">Cargando mensajes...</p>;
  }

  if (templatesQuery.error || interactionsQuery.error) {
    return (
      <p className="text-sm text-red-400">
        No se pudieron cargar los datos de mensajes e interacciones.
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <section>
        <header className="mb-4">
          <h3 className="text-xl font-semibold text-white">Plantillas</h3>
          <p className="text-sm text-slate-400">
            Bases preaprobadas para envío en WhatsApp, Email u otros canales.
          </p>
        </header>
        <Table<MessageTemplate>
          data={templatesQuery.data ?? []}
          columns={templateColumns}
          empty="Sin plantillas disponibles"
        />
      </section>
      <section>
        <header className="mb-4">
          <h3 className="text-xl font-semibold text-white">Registro de interacciones</h3>
          <p className="text-sm text-slate-400">
            Historial consolidado de conversaciones multicanal.
          </p>
        </header>
        <Table<InteractionLog>
          data={interactionsQuery.data ?? []}
          columns={interactionColumns}
          empty="Sin interacciones registradas"
        />
      </section>
    </div>
  );
}

export default MessagesPage;
