import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Dashboard } from "@/pages/Dashboard";
import { Salary } from "@/pages/Salary";
import { Ledger } from "@/pages/Ledger";
import { Budgets } from "@/pages/Budgets";
import { Analytics } from "@/pages/Analytics";
import "@/pages/pages.css";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="salary" element={<Salary />} />
        <Route path="ledger" element={<Ledger />} />
        <Route path="budgets" element={<Budgets />} />
        <Route path="analytics" element={<Analytics />} />
      </Route>
    </Routes>
  );
}
