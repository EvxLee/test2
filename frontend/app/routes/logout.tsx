import { logout } from "../auth";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";


export default function Logout() {
  const navigate = useNavigate();
  useEffect(() => {
    navigate("/");
  }, []);
  return <p className="text-center mt-10 text-gray-600">Logging out...</p>;
}
