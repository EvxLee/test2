import React from "react";

export interface Startup {
  id: number;
  name: string;
  employees?: number | null;
  status?: "Ongoing" | "On Hold" | "Archived" | "Completed" | null;
  stage?: "Angel" | "Seed" | "Series A" | "Series B" | "Venture - Unspecified" | string | null;
  industry: string;
  associatedProject: string;
  summary: string;
  profilePics?: string[];
  hasGCEDMatch?: boolean;
  gcedTeamDecision?: string | null;
}

interface CardProps {
  startup: Startup;
  onClick: () => void;
}

export default function StartupCard({ startup, onClick }: CardProps) {
  // derive a pleasant color from the startup name
  const stringToColor = (str: string) => {
    const s = String(str || "");
    let hash = 0;
    for (let i = 0; i < s.length; i++) {
      hash = s.charCodeAt(i) + ((hash << 5) - hash);
    }
    const h = Math.abs(hash) % 360; // hue
    // use HSL for vibrant but pleasant colors
    return `hsl(${h}deg 65% 50%)`;
  };

  const initials = (startup.name || "").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();
  const logoColor = stringToColor(startup.name || "");
  //  status color mapping
  const statusColor: Record<Startup["status"], string> = {
    Ongoing: "bg-green-400 text-black",
    "On Hold": "bg-yellow-400 text-black",
    Archived: "bg-gray-400 text-black",
    Completed: "bg-blue-400 text-white",
  };

  const stageColor = "bg-red-600 text-white";

  // Match vertical colors with Projects tab
  const getIndustryColor = (industry: string) => {
    const industryLower = industry.toLowerCase();
    if (/ai|artificial intelligence/i.test(industryLower)) {
      return "bg-blue-100 text-blue-800";
    } else if (/clean|cleantech|clean tech|sustainability|climate/i.test(industryLower)) {
      return "bg-green-100 text-green-800";
    } else if (/health|healthcare|medical|biotech|pharma/i.test(industryLower)) {
      return "bg-purple-100 text-purple-800";
    }
    return "bg-gray-100 text-gray-800";
  };

  const industryColor = getIndustryColor(startup.industry);

  return (
    <div
      onClick={onClick}
      className="cursor-pointer bg-white rounded-xl shadow-sm p-4 hover:shadow-md hover:scale-[1.01] transform transition-all w-full h-full flex flex-col"
    >
      {/* top section */}
      <div className="flex items-start justify-between">
        <div className="flex items-center space-x-2">
          {/* colored logo placeholder with initials */}
          <div
            className="w-8 h-8 rounded-md flex items-center justify-center text-white font-semibold"
            style={{ backgroundColor: logoColor }}
            aria-hidden
          >
            <span className="text-sm leading-none">{initials}</span>
          </div>
          <h3 className="text-lg font-semibold text-gray-900">{startup.name}</h3>
        </div>
      </div>

      {/* employees - only show if data exists */}
      {(startup.employees != null && startup.employees > 0) && (
        <div className="flex items-center gap-2 mt-2">
          {/* employee profile images */}
          <div className="flex -space-x-2">
            {startup.profilePics?.map((pic, i) => (
              <img
                key={i}
                src={pic}
                alt="profile"
                className="w-7 h-7 rounded-full border-2 border-white"
              />
            ))}
          </div>
          <p className="text-sm text-gray-600">{startup.employees} Employees</p>
        </div>
      )}

      {/* tags, status, and stage */}
      <div className="flex flex-wrap gap-2 mt-3 items-center">
        {/* GCED badge */}
        {startup.hasGCEDMatch && (
          <span className="bg-green-100 text-green-800 text-xs font-semibold px-3 py-1 rounded-full">
            GCED
          </span>
        )}

        {/* GCED Team Decision badge */}
        {startup.gcedTeamDecision && (
          <span
            className={`text-xs font-semibold px-3 py-1 rounded-full ${
              startup.gcedTeamDecision.toLowerCase() === "yes"
                ? "bg-emerald-100 text-emerald-800"
                : startup.gcedTeamDecision.toLowerCase().includes("later")
                ? "bg-amber-100 text-amber-800"
                : startup.gcedTeamDecision.toLowerCase() === "no"
                ? "bg-red-100 text-red-800"
                : "bg-gray-100 text-gray-800"
            }`}
          >
            {startup.gcedTeamDecision}
          </span>
        )}

        {/* industry chip */}
        {startup.industry && (
          <span
            className={`${industryColor} text-xs font-semibold px-3 py-1 rounded-full`}
          >
            {startup.industry}
          </span>
        )}

        {/* status - only show if valid */}
        {startup.status && statusColor[startup.status] && (
          <span
            className={`${statusColor[startup.status]} text-xs font-semibold px-3 py-1 rounded-full`}
          >
            {startup.status}
          </span>
        )}

        {/* stage - only show if valid */}
        {startup.stage && (
          <span
            className={`${stageColor} text-xs font-semibold px-3 py-1 rounded-full`}
          >
            {startup.stage}
          </span>
        )}
      </div>

      {/* associated project + summary */}
      <div className="mt-4 flex-1 flex flex-col min-h-0">
        <p className="text-sm font-semibold text-gray-900">
          Associated Project: <span className="font-normal text-gray-600">{startup.associatedProject || "—"}</span>
        </p>
        <p className="text-sm font-semibold text-gray-900 mt-1">Summary:</p>
        <div className="relative overflow-hidden max-h-[4.5rem] mt-0.5">
          <p className="text-sm font-normal text-gray-600">{startup.summary || "—"}</p>
          <div className="absolute bottom-0 left-0 right-0 h-6 bg-gradient-to-b from-transparent to-white pointer-events-none" />
        </div>
      </div>
    </div>
  );
}