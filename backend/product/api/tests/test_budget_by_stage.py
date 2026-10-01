import hashlib
import os
from unittest.mock import patch

import app as app_module


AUTH_HEADER = {"Authorization": "Bearer test-token"}


def test_budget_by_stage_falls_back_to_pjt_task_when_project_links_are_missing():
    def fake_fetch_all(sql: str, params: tuple = ()):
        assert "LEFT JOIN master_dashboard.projects p ON p.id = cs.project_id" in sql
        assert "cs.pjt_task" in sql
        assert "WHERE project_name IS NOT NULL" in sql
        assert params == ()
        return [
            {
                "project_id": "pjt:b87cbf477036229c906831eb59e80866",
                "project_name": "ExampleStartup",
                "stage_name": "4",
                "total_amount": 15000,
            },
            {
                "project_id": "pjt:0ebb4db02089017bab6fe11338084a51",
                "project_name": "Skillco",
                "stage_name": "5",
                "total_amount": 250000,
            },
        ]

    with patch.dict(os.environ, {"INGEST_API_TOKEN": "test-token"}, clear=False):
        app = app_module.create_app()
        app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})

        with patch.object(app_module, "fetch_all", side_effect=fake_fetch_all):
            response = app.test_client().get(
                "/atlas/display/budget-by-stage",
                headers=AUTH_HEADER,
            )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 2
    assert payload["rows"][0]["project_name"] == "ExampleStartup"
    assert payload["rows"][0]["stage_name"] == "4"
    assert payload["rows"][0]["total_amount"] == 15000.0


def test_budget_by_stage_accepts_synthetic_project_ids_for_filtered_requests():
    synthetic_id = "pjt:" + hashlib.md5("examplestartup".encode("utf-8")).hexdigest()

    def fake_fetch_all(sql: str, params: tuple = ()):
        assert "project_id::text = %s" in sql
        assert "md5(LOWER(project_name))" in sql
        assert params == (synthetic_id, synthetic_id)
        return [
            {
                "project_id": synthetic_id,
                "project_name": "ExampleStartup",
                "stage_name": "4",
                "total_amount": 15000,
            }
        ]

    with patch.dict(os.environ, {"INGEST_API_TOKEN": "test-token"}, clear=False):
        app = app_module.create_app()
        app.config.update({"TESTING": True, "RATELIMIT_ENABLED": False})

        with patch.object(app_module, "fetch_all", side_effect=fake_fetch_all):
            response = app.test_client().get(
                f"/atlas/display/budget-by-stage?project_id={synthetic_id}",
                headers=AUTH_HEADER,
            )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["count"] == 1
    assert payload["rows"][0]["project_id"] == synthetic_id
