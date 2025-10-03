import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactNode, useMemo } from "react";
import { useRoutes } from "react-router-dom";

import Layout from "./components/Layout";
import CampaignsPage from "./pages/CampaignsPage";
import CustomersPage from "./pages/CustomersPage";
import DashboardPage from "./pages/DashboardPage";
import IntegrationsPage from "./pages/IntegrationsPage";
import MessagesPage from "./pages/MessagesPage";
import SegmentsPage from "./pages/SegmentsPage";

const queryClient = new QueryClient();

type RouteElement = ReactNode;

const routeConfig = [
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "customers", element: <CustomersPage /> },
      { path: "campaigns", element: <CampaignsPage /> },
      { path: "messages", element: <MessagesPage /> },
      { path: "segments", element: <SegmentsPage /> },
      { path: "integrations", element: <IntegrationsPage /> },
    ],
  },
];

function App() {
  const element = useRoutes(routeConfig);

  return (
    <QueryClientProvider client={queryClient}>{element}</QueryClientProvider>
  );
}

export default App;
