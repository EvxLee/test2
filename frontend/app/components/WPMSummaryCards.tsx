import { useState, useMemo } from "react";
import { countByCurrentStage } from "~/lib/projects";
import type Project from "~/types/Project";

type StageNum = 2 | 3 | 4 | 5;
type Goals = Partial<Record<StageNum, number>>;

const DEFAULT_GOALS: Record<StageNum, number> = {
  2: 10,
  3: 10,
  4: 10,
  5: 10,
};

const STAGE_LABEL: Record<StageNum, string> = {
  2: "Stage 2",
  3: "Stage 3",
  4: "Stage 4",
  5: "Stage 5",
};

const STAGE_COLOR: Record<StageNum, string> = {
  2: "text-[#8B1E2F]",
  3: "text-green-600",
  4: "text-blue-600",
  5: "text-purple-600",
};

interface WPMSummaryCardsProps {
  data?: Project[];
  initialGoals?: Goals;
  editable?: boolean;
  onGoalsChange?: (goals: Record<StageNum, number>) => void;
}

const WPMSummaryCards = ({
  data,
  initialGoals,
  editable = true,
  onGoalsChange,
}: WPMSummaryCardsProps) => {
  const [goals, setGoals] = useState<Record<StageNum, number>>({
    ...DEFAULT_GOALS,
    ...(initialGoals as Goals),
  });

  const counts = useMemo(
    () => countByCurrentStage(data ?? []),
    [data]
  );

  const [editingStage, setEditingStage] = useState<StageNum | null>(null);
  const [draft, setDraft] = useState<string>("");

  const beginEdit = (stage: StageNum) => {
    if (!editable) return;
    setEditingStage(stage);
    setDraft(String(goals[stage] ?? 0));
  };

  const commitEdit = () => {
    if (editingStage == null) return;
    const parsed = Number(draft);
    const next = Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : goals[editingStage];
    const newGoals = { ...goals, [editingStage]: next } as Record<StageNum, number>;
    setGoals(newGoals);
    setEditingStage(null);
    onGoalsChange?.(newGoals);
  };

  const cancelEdit = () => {
    setEditingStage(null);
    setDraft("");
  };

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 mt-6">
      {(Object.keys(goals) as unknown as StageNum[]).map((stage) => (
        <div key={stage} className="bg-white text-center p-5 rounded-lg shadow">
          <p className="text-gray-500 text-sm">{STAGE_LABEL[stage]}</p>
          <p className="text-gray-500 text-sm">Achieved / Goal 25'</p>

          {/* Achieved / Goal */}
          <div className="flex items-baseline justify-center gap-2">
            <span className={`text-3xl font-bold ${STAGE_COLOR[stage]}`}>
              {counts[stage]}
            </span>
            <span className="text-3xl font-bold">/</span>

            {editingStage === stage ? (
              <input
                type="number"
                min={0}
                className={`text-3xl font-bold w-20 text-center border-b border-gray-300 focus:outline-none focus:border-gray-500 ${STAGE_COLOR[stage]}`}
                autoFocus
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitEdit}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitEdit();
                  if (e.key === "Escape") cancelEdit();
                }}
              />
            ) : (
              <button
                type="button"
                className={`text-3xl font-bold hover:underline decoration-dotted ${STAGE_COLOR[stage]}`}
                onDoubleClick={() => beginEdit(stage)}
                title={editable ? "Double-click to edit goal" : undefined}
              >
                {goals[stage]}
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default WPMSummaryCards;