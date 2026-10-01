export type ProjectStatus = "Ongoing" | "On Hold" | "Archived";
export type ProjectVertical = "Healthtech" | "AI" | "Cleantech";

export default interface Project {
  id: string;
  name: string;
  description: string;
  startupName: string;

  stage: 2 | 3 | 4 | 5 | null;

  status: string;

  statusCategory: ProjectStatus;

  vertical: ProjectVertical;
  deadline?: string | Date;

  owner: string;
  stagesCompletedCY: (2 | 3 | 4 | 5)[];
}
