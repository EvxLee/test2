import { NavLink, useLocation, Link } from "react-router-dom";
import { useState } from "react";
import { logout, hasPartnerRole } from "../auth";

export default function Sidebar() {
  const [isProjectsOpen, setIsProjectsOpen] = useState(false);

  return (
    <aside
      className="
        w-64 sticky top-0 h-screen
        bg-gradient-to-b from-red-600 via-red-500 to-rose-400
        text-white flex flex-col shadow-2xl
      "
    >
      <div className="p-6 border-b border-white/20">
        <Link to="/app/dashboard" className="text-3xl font-bold tracking-tight hover:opacity-90">
          Atlas
        </Link>
        <p className="text-xs text-white/70 mt-1">Internal Dashboard</p>
      </div>

      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        <NavLink
          to="/app/dashboard"
          end
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Main Dashboard
        </NavLink>

        <NavLink
          to="/app/projects"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Projects
        </NavLink>

        <NavLink
          to="/app/contracts"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Contracts
        </NavLink>

        <NavLink
          to="/app/documents"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Documents
        </NavLink>

        <NavLink
          to="/app/partnerstartups"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Partner Startups
        </NavLink>

        <NavLink
          to="/app/korean"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Regional
        </NavLink>

        <NavLink
          to="/app/partner-data-to-board"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Pre-cap Board Generator
        </NavLink>

        <NavLink
          to="/app/monday-importer"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          Monday Data Importer
        </NavLink>

        <NavLink
          to="/app/pitchbook-importer"
          className={({ isActive }) =>
            `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
              isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
            }`
          }
        >
          PitchBook Data Importer
        </NavLink>

        {hasPartnerRole() && (
          <NavLink
            to="/app/partner-upload"
            className={({ isActive }) =>
              `block px-4 py-3 rounded-lg font-medium text-base transition-all ${
                isActive ? "bg-white/25 shadow-lg" : "hover:bg-white/10 hover:translate-x-1"
              }`
            }
          >
            Duplicate Checker
          </NavLink>
        )}

      </nav>

      <div className="p-4 border-t border-white/20">
        <button
          onClick={logout}
          className="block w-full px-4 py-3 text-center rounded-lg bg-white/10 hover:bg-white/20 transition-all font-medium"
        >
          Logout
        </button>
      </div>
    </aside>
  );
}