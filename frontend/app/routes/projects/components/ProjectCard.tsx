import type Project from "app/types/Project.ts";;

export default function ProjectCard({ project }: { project: Project }) {
  // Color mapping for verticals (same as partner startups)
  const verticalColors: Record<string, string> = {
    AI: "bg-blue-100 text-blue-800",
    Cleantech: "bg-green-100 text-green-800",
    Healthtech: "bg-purple-100 text-purple-800",
  };

  const verticalColor = verticalColors[project.vertical] || "bg-gray-100 text-gray-800";

  // Remove parenthetical text and normalize to whole-number stage (e.g., "Stage 2.1 (POC)" -> "Stage 2")
  const stageDisplay = project.status
    .replace(/\s*\([^)]*\)/g, '')
    .replace(/(\bStage\s+\d+)\.\d+/gi, '$1');

  return (
    <article className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md h-[180px] flex flex-col">
      <header className="mb-2 flex items-start justify-between gap-2 flex-shrink-0">
        <div className="min-w-0 flex-1">
          <h3 className="text-base font-semibold text-gray-900 truncate">{project.name}</h3>
          <p className="text-sm text-gray-500 truncate">{project.startupName}</p>
        </div>
        <div className="flex gap-2 flex-shrink-0">
          <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${verticalColor}`}>
            {project.vertical}
          </span>
          <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700 whitespace-nowrap">
            {stageDisplay}
          </span>
        </div>
      </header>
      <div className="relative flex-1 overflow-hidden">
        <p className="text-sm text-gray-700 leading-relaxed">{project.description}</p>
        <div className="absolute bottom-0 left-0 right-0 h-10 bg-gradient-to-t from-white to-transparent pointer-events-none" />
      </div>
    </article>
  );
}
