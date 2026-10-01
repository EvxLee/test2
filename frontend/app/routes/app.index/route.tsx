import { redirect } from "react-router"; // not react-router-dom

export const loader = () => redirect("/app/dashboard");

export default function AppIndex() { return null; }