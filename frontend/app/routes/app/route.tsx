import { Outlet } from "react-router-dom";
import { redirect } from "react-router";
import Sidebar from "../../components/Sidebar";
import { isLoggedIn } from "../../auth";
import Chatbot from "../../components/Chatbot";
import { useChatContext } from "../../contexts/ChatContext";

export function clientLoader() {
  if (!isLoggedIn()) throw redirect("/");
  return null;
}

export default function AppLayout() {
  const { context } = useChatContext();

  return (
    <div className="h-screen overflow-hidden flex">
      <Sidebar />
      <main className="flex-1 h-full overflow-y-auto p-6">
        <Outlet />
      </main>
      <div className="absolute top-4 right-4 z-50">
        <Chatbot context={context} />
      </div>
    </div>
  );
}
