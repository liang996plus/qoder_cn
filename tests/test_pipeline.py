"""Pipeline 引擎测试"""

import base64
import pytest


class TestScenarioLoader:
    def test_load_scenario(self):
        from app.core.scenario_loader import load_scenario

        scenario = load_scenario("sample_analysis")
        assert scenario.scenario_id == "sample_analysis"
        assert scenario.name == "示例分析场景"
        assert len(scenario.data_sources) == 1
        assert len(scenario.pipeline) >= 2
        assert len(scenario.outputs) >= 2

    def test_load_nonexistent_scenario(self):
        from app.core.scenario_loader import load_scenario
        from app.core.errors import AppException

        with pytest.raises(AppException, match="场景配置不存在"):
            load_scenario("nonexistent_scenario")

    def test_list_scenarios(self):
        from app.core.scenario_loader import list_scenarios

        scenarios = list_scenarios()
        assert len(scenarios) >= 1
        ids = [s["scenario_id"] for s in scenarios]
        assert "sample_analysis" in ids


class TestPipelineAPI:
    def test_list_scenarios_endpoint(self, client):
        resp = client.get("/api/v1/pipeline/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert len(data["data"]) >= 1
        ids = [s["scenario_id"] for s in data["data"]]
        assert "sample_analysis" in ids

    def test_run_pipeline_e2e(self, client):
        """端到端测试：上传 CSV -> 清洗 -> 统计 -> 输出"""
        csv_content = "name,age,score\nAlice,25,88.5\nBob,30,92.0\nCharlie,28,76.3\nDiana,35,95.1\n"
        b64_content = base64.b64encode(csv_content.encode("utf-8")).decode("utf-8")

        request_body = {
            "scenario_id": "sample_analysis",
            "params": {
                "file_content": b64_content,
                "filename": "test_data.csv",
                "sort_column": "score",
            },
        }

        resp = client.post(
            "/api/v1/pipeline/run",
            json=request_body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

        result = data["data"]
        assert result["scenario_id"] == "sample_analysis"

        # 检查步骤执行
        steps = result["steps"]
        assert len(steps) >= 2
        # 至少有 clean 和 statistics 步骤成功
        success_steps = [s for s in steps if s["status"] == "success"]
        assert len(success_steps) >= 2

        # 检查输出
        outputs = result["outputs"]
        assert len(outputs) >= 2

        # 检查摘要输出
        summary_output = next(
            (o for o in outputs if o["type"] == "summary"), None
        )
        assert summary_output is not None
        assert summary_output["data"]["row_count"] == 4

        # 检查文件输出
        file_output = next(
            (o for o in outputs if o["type"] == "file"), None
        )
        assert file_output is not None
        assert "download_url" in file_output["data"]

        # 检查总耗时
        assert result["total_duration_ms"] > 0

    def test_run_nonexistent_scenario(self, client):
        request_body = {
            "scenario_id": "nonexistent",
            "params": {},
        }
        resp = client.post(
            "/api/v1/pipeline/run",
            json=request_body,
        )
        data = resp.json()
        assert data["code"] == 6001  # SCENARIO_NOT_FOUND
