SET search_path TO master_dashboard;
CREATE OR REPLACE VIEW vw_master_dashboard AS
SELECT
  p.id,
  p.project_code,
  p.name                    AS pjt_name,
  v.vertical_name           AS vertical,
  COALESCE(
    l.display_name,
    CONCAT_WS(', ', l.city, l.state_region, l.country)
  )                         AS location,
  st.stage_name             AS current_stage,
  STRING_AGG(DISTINCT pe.full_name, ', ') AS owners
FROM projects p
LEFT JOIN verticals       v  ON v.id = p.vertical_id
LEFT JOIN locations       l  ON l.id = p.location_id
LEFT JOIN project_stages  s  ON s.id = p.current_stage_id
LEFT JOIN stage_types     st ON st.id = s.stage_type_id
LEFT JOIN project_owners  po ON po.project_id = p.id
LEFT JOIN people          pe ON pe.id = po.person_id
GROUP BY
  p.id, p.project_code, p.name,
  v.vertical_name,
  l.display_name, l.city, l.state_region, l.country,
  st.stage_name;
   