"""数据处理 API 测试"""

import io
import pytest


class TestHealthCheck:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "healthy"


class TestParse:
    def test_parse_csv(self, client):
        csv_content = "name,age,score\nAlice,25,88\nBob,30,92\n"
        files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post("/api/v1/data/parse", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["file_type"] == "csv"
        assert data["data"]["meta"]["row_count"] == 2
        assert "name" in data["data"]["columns"]

    def test_parse_json(self, client):
        json_content = '[{"name":"Alice","age":25},{"name":"Bob","age":30}]'
        files = {"file": ("test.json", io.BytesIO(json_content.encode()), "application/json")}
        resp = client.post("/api/v1/data/parse", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["meta"]["row_count"] == 2

    def test_parse_unsupported_format(self, client):
        files = {"file": ("test.xyz", io.BytesIO(b"data"), "application/octet-stream")}
        resp = client.post("/api/v1/data/parse", files=files)
        body = resp.json()
        assert body["code"] == 2001


class TestQuery:
    def test_basic_select(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "sql": "SELECT name, score FROM df WHERE score > 85 ORDER BY score DESC",
        }
        resp = client.post("/api/v1/data/query", json=request_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["meta"]["row_count"] == 3  # Alice(88.5), Bob(92), Diana(95.1)

    def test_sql_injection_blocked(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "sql": "DROP TABLE df",
        }
        resp = client.post("/api/v1/data/query", json=request_body)
        body = resp.json()
        assert body["code"] == 2002


class TestFilter:
    def test_filter_eq(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "conditions": [{"column": "city", "operator": "eq", "value": "Beijing"}],
            "logic": "and",
        }
        resp = client.post("/api/v1/data/filter", json=request_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["meta"]["row_count"] == 2

    def test_filter_gt(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "conditions": [{"column": "age", "operator": "gt", "value": 28}],
            "logic": "and",
        }
        resp = client.post("/api/v1/data/filter", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["meta"]["row_count"] == 2  # Bob(30), Diana(35)


class TestAggregate:
    def test_groupby_sum(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "group_by": ["city"],
            "agg_columns": ["score"],
            "agg_funcs": ["sum", "mean"],
        }
        resp = client.post("/api/v1/data/aggregate", json=request_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "score_sum" in data["data"]["columns"]
        assert "score_mean" in data["data"]["columns"]


class TestSort:
    def test_sort_desc(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "sort_by": ["score"],
            "ascending": False,
        }
        resp = client.post("/api/v1/data/sort", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        # 最高分在第一行
        first_row = data["data"]["data"][0]
        assert first_row[2] == 95.1  # Diana


class TestDedup:
    def test_dedup_by_city(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "subset": ["city"],
            "keep": "first",
        }
        resp = client.post("/api/v1/data/dedup", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["meta"]["row_count"] == 3  # Beijing, Shanghai, Guangzhou


class TestClean:
    def test_fill_na(self, client):
        request_body = {
            "dataframe": {
                "columns": ["a", "b"],
                "data": [[1, None], [None, 2], [3, 4]],
            },
            "operations": [
                {"operation": "fill_na", "column": None, "params": {"value": 0}},
            ],
        }
        resp = client.post("/api/v1/data/clean", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert None not in data["data"]["data"][0]
        assert None not in data["data"]["data"][1]


class TestStatistics:
    def test_descriptive(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "stat_type": "descriptive",
        }
        resp = client.post("/api/v1/data/statistics", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert "stat" in data["data"]["columns"]

    def test_correlation(self, client, sample_dataframe_input):
        request_body = {
            **sample_dataframe_input,
            "stat_type": "correlation",
            "columns": ["age", "score"],
        }
        resp = client.post("/api/v1/data/statistics", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert "column" in data["data"]["columns"]
