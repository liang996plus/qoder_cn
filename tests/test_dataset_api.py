"""数据集入库 API 测试"""

import io
import pytest


# ── 辅助工具 ───────────────────────────────────────────────────────

def _upload_csv(client, filename="test.csv", table_name=None, description=""):
    """上传一个简单 CSV 并入库，返回响应 JSON"""
    csv_content = "name,age,score\nAlice,25,88\nBob,30,92\nCharlie,28,76\n"
    files = {"file": (filename, io.BytesIO(csv_content.encode()), "text/csv")}
    data = {}
    if table_name is not None:
        data["table_name"] = table_name
    if description:
        data["description"] = description
    resp = client.post("/api/v1/data/ingest", files=files, data=data)
    return resp


# ── 入库接口测试 ──────────────────────────────────────────────────

class TestIngest:
    def test_ingest_csv(self, client):
        resp = _upload_csv(client, table_name="test_ingest_basic")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["table_name"] == "test_ingest_basic"
        assert data["row_count"] == 3
        assert data["column_count"] == 3
        assert "name" in data["columns"]
        assert data["file_type"] == "csv"
        assert "id" in data

    def test_ingest_auto_table_name(self, client):
        """不传 table_name 时应自动生成"""
        resp = _upload_csv(client)
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["table_name"].startswith("ds_")

    def test_ingest_with_description(self, client):
        resp = _upload_csv(client, table_name="test_ingest_desc", description="测试数据集")
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["description"] == "测试数据集"

    def test_ingest_unsupported_format(self, client):
        files = {"file": ("bad.xyz", io.BytesIO(b"data"), "application/octet-stream")}
        resp = client.post("/api/v1/data/ingest", files=files)
        body = resp.json()
        assert body["code"] == 2001  # FILE_PARSE_ERROR

    def test_ingest_json(self, client):
        json_content = '[{"x":1,"y":2},{"x":3,"y":4}]'
        files = {"file": ("data.json", io.BytesIO(json_content.encode()), "application/json")}
        resp = client.post("/api/v1/data/ingest", files=files, data={"table_name": "test_json_ds"})
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["row_count"] == 2
        assert body["data"]["file_type"] == "json"


# ── 追加模式测试 ─────────────────────────────────────────────────

class TestAppendMode:
    def _create_base_dataset(self, client, table_name="append_base_ds"):
        """先建一个基础数据集"""
        csv_content = "name,age,score\nAlice,25,88\nBob,30,92\n"
        files = {"file": ("base.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"table_name": table_name, "mode": "create"},
        )
        assert resp.json()["code"] == 0
        return resp.json()["data"]

    def test_append_rows(self, client):
        base = self._create_base_dataset(client, table_name="append_rows_ds")
        assert base["row_count"] == 2

        # 追加 2 行
        csv_append = "name,age,score\nCharlie,28,76\nDiana,35,95\n"
        files = {"file": ("extra.csv", io.BytesIO(csv_append.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"table_name": "append_rows_ds", "mode": "append"},
        )
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["mode"] == "append"
        # id 应该与原始数据集相同
        assert body["data"]["id"] == base["id"]

        # 查询验证总行数
        ds_id = base["id"]
        resp2 = client.post(
            f"/api/v1/data/datasets/{ds_id}/query",
            json={"sql": 'SELECT COUNT(*) AS cnt FROM "append_rows_ds"'},
        )
        count_row = resp2.json()["data"]["data"][0]
        assert count_row[0] == 4  # 2 + 2

    def test_append_table_not_found(self, client):
        csv_content = "name,age,score\nAlice,25,88\n"
        files = {"file": ("x.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"table_name": "nonexistent_table", "mode": "append"},
        )
        body = resp.json()
        assert body["code"] == 1003  # RESOURCE_NOT_FOUND

    def test_append_missing_column(self, client):
        self._create_base_dataset(client, table_name="append_col_ds")
        # 追加时缺少 score 列
        csv_bad = "name,age\nX,20\n"
        files = {"file": ("bad.csv", io.BytesIO(csv_bad.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"table_name": "append_col_ds", "mode": "append"},
        )
        body = resp.json()
        assert body["code"] == 2005  # DATASET_ERROR

    def test_append_without_table_name(self, client):
        csv_content = "name,age,score\nAlice,25,88\n"
        files = {"file": ("x.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"mode": "append"},  # 不传 table_name
        )
        body = resp.json()
        assert body["code"] == 2005  # DATASET_ERROR

    def test_invalid_mode(self, client):
        csv_content = "name,age,score\nAlice,25,88\n"
        files = {"file": ("x.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = client.post(
            "/api/v1/data/ingest",
            files=files,
            data={"mode": "overwrite"},  # 无效 mode
        )
        body = resp.json()
        assert body["code"] == 2005


# ── 列表接口测试 ──────────────────────────────────────────────────

class TestListDatasets:
    def test_list_after_ingest(self, client):
        # 先入库一个
        _upload_csv(client, table_name="list_test_ds")
        resp = client.get("/api/v1/data/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        tables = [d["table_name"] for d in body["data"]]
        assert "list_test_ds" in tables

    def test_list_returns_metadata(self, client):
        _upload_csv(client, table_name="meta_test_ds", description="元数据测试")
        resp = client.get("/api/v1/data/datasets")
        datasets = resp.json()["data"]
        found = next(d for d in datasets if d["table_name"] == "meta_test_ds")
        assert found["row_count"] == 3
        assert found["filename"] == "test.csv"


# ── 详情接口测试 ──────────────────────────────────────────────────

class TestGetDataset:
    def _get_dataset_id(self, client, table_name="get_test_ds"):
        _upload_csv(client, table_name=table_name)
        datasets = client.get("/api/v1/data/datasets").json()["data"]
        return next(d["id"] for d in datasets if d["table_name"] == table_name)

    def test_get_dataset_detail(self, client):
        ds_id = self._get_dataset_id(client)
        resp = client.get(f"/api/v1/data/datasets/{ds_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["id"] == ds_id
        assert body["data"]["table_name"] == "get_test_ds"

    def test_get_dataset_with_preview(self, client):
        ds_id = self._get_dataset_id(client, table_name="preview_test_ds")
        resp = client.get(f"/api/v1/data/datasets/{ds_id}?preview=2")
        body = resp.json()
        assert body["code"] == 0
        preview = body["data"]["preview"]
        assert len(preview) == 2  # 只取前 2 行

    def test_get_nonexistent_dataset(self, client):
        resp = client.get("/api/v1/data/datasets/nonexistent_id")
        body = resp.json()
        assert body["code"] == 1003  # RESOURCE_NOT_FOUND


# ── 查询接口测试 ──────────────────────────────────────────────────

class TestQueryDataset:
    def _ingest_and_get_table(self, client, table_name="query_test_ds"):
        _upload_csv(client, table_name=table_name)
        datasets = client.get("/api/v1/data/datasets").json()["data"]
        ds = next(d for d in datasets if d["table_name"] == table_name)
        return ds["id"], table_name

    def test_select_all(self, client):
        ds_id, table_name = self._ingest_and_get_table(client)
        resp = client.post(
            f"/api/v1/data/datasets/{ds_id}/query",
            json={"sql": f'SELECT * FROM "{table_name}"'},
        )
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["row_count"] == 3
        assert "name" in body["data"]["columns"]

    def test_select_with_where(self, client):
        ds_id, table_name = self._ingest_and_get_table(client, table_name="query_where_ds")
        resp = client.post(
            f"/api/v1/data/datasets/{ds_id}/query",
            json={"sql": f'SELECT name FROM "{table_name}" WHERE age > 27'},
        )
        body = resp.json()
        assert body["code"] == 0
        # Bob(30) and Charlie(28)
        assert body["data"]["row_count"] == 2

    def test_dangerous_sql_blocked(self, client):
        ds_id, _ = self._ingest_and_get_table(client, table_name="query_safe_ds")
        resp = client.post(
            f"/api/v1/data/datasets/{ds_id}/query",
            json={"sql": 'DROP TABLE "query_safe_ds"'},
        )
        body = resp.json()
        assert body["code"] == 2002  # SQL_EXECUTION_ERROR

    def test_query_nonexistent_dataset(self, client):
        resp = client.post(
            "/api/v1/data/datasets/no_such_id/query",
            json={"sql": "SELECT 1"},
        )
        body = resp.json()
        assert body["code"] == 1003


# ── 删除接口测试 ──────────────────────────────────────────────────

class TestDeleteDataset:
    def _get_dataset_id(self, client, table_name):
        _upload_csv(client, table_name=table_name)
        datasets = client.get("/api/v1/data/datasets").json()["data"]
        return next(d["id"] for d in datasets if d["table_name"] == table_name)

    def test_delete_dataset(self, client):
        ds_id = self._get_dataset_id(client, table_name="to_delete_ds")
        resp = client.delete(f"/api/v1/data/datasets/{ds_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["deleted"] is True

        # 再次查询应该 404
        resp2 = client.get(f"/api/v1/data/datasets/{ds_id}")
        assert resp2.json()["code"] == 1003

    def test_delete_nonexistent_dataset(self, client):
        resp = client.delete("/api/v1/data/datasets/nonexistent_id")
        body = resp.json()
        assert body["code"] == 1003
