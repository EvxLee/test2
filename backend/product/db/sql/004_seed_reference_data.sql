-- Seed Reference Data --
SET search_path TO master_dashboard;
INSERT INTO stage_types (id, stage_name)
SELECT gen_random_uuid(), v
FROM (VALUES ('Explore'),('Validate'),('Incubate'),('Pilot'),('Scale')) AS t(v)
WHERE NOT EXISTS (SELECT 1 FROM stage_types s WHERE s.stage_name = t.v);

-- Optional verticals --
INSERT INTO verticals (id, vertical_name)
SELECT gen_random_uuid(), v
FROM (VALUES ('AI'),('HealthTech'),('CleanTech')) AS t(v)
WHERE NOT EXISTS (SELECT 1 FROM verticals x WHERE x.vertical_name = t.v);