import React from "react";

interface WPMProject {
  id: string;
  name: string;
  owner: string;
  vertical: "AI" | "Cleantech" | "Healthtech";
  deadline: string;
  stage: number;
}

//similar to WPMSummary, connect this to the backend database for real-time analysis instead of constants. BACK END TEAM TASK

const wpmProjects: WPMProject[] = [
  {
    id: "1",
    name: "CarbonTrack",
    owner: "John Smith",
    vertical: "Cleantech",
    deadline: "2024-03-15",
    stage: 1,
  },
  {
    id: "2",
    name: "AI Analytics Platform",
    owner: "Sarah Johnson",
    vertical: "AI",
    deadline: "2024-03-20",
    stage: 1,
  },
  {
    id: "3",
    name: "Health Monitoring System",
    owner: "Michael Chen",
    vertical: "Healthtech",
    deadline: "2024-03-18",
    stage: 1,
  },
  {
    id: "4",
    name: "Solar Grid Optimization",
    owner: "Emma Davis",
    vertical: "Cleantech",
    deadline: "2024-04-01",
    stage: 2,
  },
  {
    id: "5",
    name: "Machine Learning Framework",
    owner: "David Wilson",
    vertical: "AI",
    deadline: "2024-04-05",
    stage: 2,
  },
  {
    id: "6",
    name: "Telemedicine Platform",
    owner: "Lisa Anderson",
    vertical: "Healthtech",
    deadline: "2024-04-10",
    stage: 2,
  },
  {
    id: "7",
    name: "Wind Energy Solutions",
    owner: "Robert Brown",
    vertical: "Cleantech",
    deadline: "2024-04-25",
    stage: 3,
  },
  {
    id: "8",
    name: "Neural Network API",
    owner: "Jennifer Lee",
    vertical: "AI",
    deadline: "2024-04-28",
    stage: 3,
  },
  {
    id: "9",
    name: "Patient Data Analytics",
    owner: "Thomas Miller",
    vertical: "Healthtech",
    deadline: "2024-05-01",
    stage: 3,
  },
  {
    id: "10",
    name: "Smart Grid Integration",
    owner: "Patricia Garcia",
    vertical: "Cleantech",
    deadline: "2024-05-15",
    stage: 4,
  },
  {
    id: "11",
    name: "Computer Vision System",
    owner: "James Martinez",
    vertical: "AI",
    deadline: "2024-05-20",
    stage: 4,
  },
  {
    id: "12",
    name: "Digital Therapeutics",
    owner: "Maria Rodriguez",
    vertical: "Healthtech",
    deadline: "2024-05-25",
    stage: 5,
  },
];

const getVerticalColor = (vertical: string) => {
  switch (vertical) {
    case "AI":
      return "bg-blue-500";
    case "Cleantech":
      return "bg-green-500";
    case "Healthtech":
      return "bg-purple-500";
    default:
      return "bg-gray-500";
  }
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
};

const WPMTable = () => {
  const [openStages, setOpenStages] = React.useState<Set<number>>(new Set());

  const toggleStage = (stage: number) => {
    setOpenStages((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(stage)) {
        newSet.delete(stage);
      } else {
        newSet.add(stage);
      }
      return newSet;
    });
  };
  const projectsByStage = wpmProjects.reduce((acc, project) => {
    if (project.stage <= 5) {
      if (!acc[project.stage]) {
        acc[project.stage] = [];
      }
      acc[project.stage].push(project);
    }
    return acc;
  }, {} as Record<number, WPMProject[]>);

  const stages = Object.keys(projectsByStage)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="bg-white rounded-b-lg overflow-hidden">
      {stages.map((stage) => {
        const isOpen = openStages.has(stage);
        const projectCount = projectsByStage[stage].length;
        
        return (
          <div key={stage} className="border-b border-gray-200 last:border-b-0">
            <button
              onClick={() => toggleStage(stage)}
              className="w-full bg-gray-100 px-6 py-3 border-b border-gray-200 hover:bg-gray-200 transition-colors flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold text-gray-800">
                  Stage {stage}
                </h3>
                <span className="text-sm text-gray-500">
                  ({projectCount} {projectCount === 1 ? 'project' : 'projects'})
                </span>
              </div>
              <svg
                className={`w-5 h-5 text-gray-600 transition-transform ${
                  isOpen ? "transform rotate-180" : ""
                }`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>
            {isOpen && (
              <div className="overflow-hidden">
                <table className="w-full border-collapse">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="p-3 text-left font-semibold text-gray-700">
                  Project Name
                </th>
                <th className="p-3 text-left font-semibold text-gray-700">
                  Owner
                </th>
                <th className="p-3 text-left font-semibold text-gray-700">
                  Vertical
                </th>
                <th className="p-3 text-left font-semibold text-gray-700">
                  Deadline
                </th>
              </tr>
            </thead>
            <tbody>
              {projectsByStage[stage].map((project) => (
                <tr
                  key={project.id}
                  className="border-b hover:bg-gray-50 transition-colors"
                >
                  <td className="p-3 font-medium text-gray-900">
                    {project.name}
                  </td>
                  <td className="p-3 text-gray-700">{project.owner}</td>
                  <td className="p-3">
                    <span
                      className={`${getVerticalColor(
                        project.vertical
                      )} text-white px-3 py-1 rounded-md text-sm font-medium`}
                    >
                      {project.vertical}
                    </span>
                  </td>
                  <td className="p-3 text-gray-700">
                    {formatDate(project.deadline)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
        </div>
      );
      })}
    </div>
  );
};

export default WPMTable;
