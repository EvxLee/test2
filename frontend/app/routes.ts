import { type RouteConfig, index, route, prefix } from "@react-router/dev/routes";

export default [
  index("./routes/home.tsx"),
  route("logout", "./routes/logout.tsx"),

  route("app", "./routes/app/route.tsx", [
    index("./routes/app.index/route.tsx"),
    route("dashboard", "./routes/MainDashboard.tsx"),
    route("partnerstartups", "./routes/partnerstartups.tsx"),
    route("korean", "./routes/korean.tsx"),
    route("partner-data-to-board", "./routes/partnerDataToBoard.tsx"),
    route("projects", "./routes/projects.tsx"),
    route("contracts", "./routes/contracts.tsx"),
    route("documents", "./routes/documents.tsx"),
    route("monday-importer", "./routes/mondayImporter.tsx"),
    route("pitchbook-importer", "./routes/pitchbookImporter.tsx"),
    route("partner-upload", "./routes/partner-upload.tsx"),
  ]),

] satisfies RouteConfig;
