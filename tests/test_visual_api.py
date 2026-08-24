"""可视化 API 测试"""


class TestChart:
    def test_bar_chart_png(self, client):
        request_body = {
            "dataframe": {
                "columns": ["product", "sales"],
                "data": [
                    ["A", 100],
                    ["B", 200],
                    ["C", 150],
                ],
            },
            "config": {
                "chart_type": "bar",
                "x": "product",
                "y": "sales",
                "title": "Sales by Product",
            },
            "output_format": "png",
        }
        resp = client.post("/api/v1/visual/chart", json=request_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["image_base64"] is not None
        assert data["data"]["output_format"] == "png"
        assert data["data"]["filename"] is not None

    def test_line_chart_svg(self, client):
        request_body = {
            "dataframe": {
                "columns": ["month", "value"],
                "data": [
                    ["Jan", 10],
                    ["Feb", 20],
                    ["Mar", 15],
                    ["Apr", 30],
                ],
            },
            "config": {
                "chart_type": "line",
                "x": "month",
                "y": "value",
                "title": "Monthly Trend",
            },
            "output_format": "svg",
        }
        resp = client.post("/api/v1/visual/chart", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["image_base64"] is not None
        assert "<svg" in data["data"]["image_base64"]

    def test_pie_chart(self, client):
        request_body = {
            "dataframe": {
                "columns": ["category", "amount"],
                "data": [
                    ["Food", 40],
                    ["Transport", 20],
                    ["Other", 15],
                ],
            },
            "config": {
                "chart_type": "pie",
                "x": "category",
                "y": "amount",
                "title": "Expense Distribution",
            },
            "output_format": "png",
        }
        resp = client.post("/api/v1/visual/chart", json=request_body)
        data = resp.json()
        assert data["code"] == 0

    def test_unsupported_chart_type(self, client):
        """使用有效枚举值但代码不支持的情况已不存在，
        测试传入非法 chart_type 应返回 422"""
        request_body = {
            "dataframe": {
                "columns": ["x", "y"],
                "data": [["a", 1]],
            },
            "config": {
                "chart_type": "invalid_type",
            },
            "output_format": "png",
        }
        resp = client.post("/api/v1/visual/chart", json=request_body)
        assert resp.status_code == 422

    def test_html_chart(self, client):
        request_body = {
            "dataframe": {
                "columns": ["name", "value"],
                "data": [
                    ["A", 10],
                    ["B", 20],
                    ["C", 30],
                ],
            },
            "config": {
                "chart_type": "bar",
                "x": "name",
                "y": "value",
                "title": "HTML Chart",
            },
            "output_format": "html",
        }
        resp = client.post("/api/v1/visual/chart", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["html_content"] is not None
        assert "plotly" in data["data"]["html_content"]


class TestTable:
    def test_basic_table(self, client):
        request_body = {
            "dataframe": {
                "columns": ["name", "score"],
                "data": [
                    ["Alice", 88.5],
                    ["Bob", 92.0],
                    ["Charlie", 76.3],
                ],
            },
        }
        resp = client.post("/api/v1/visual/table", json=request_body)
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert "<table" in data["data"]["html"]
        assert data["data"]["row_count"] == 3

    def test_table_with_config(self, client):
        request_body = {
            "dataframe": {
                "columns": ["name", "score"],
                "data": [
                    ["Alice", 88.5],
                    ["Bob", 92.0],
                    ["Charlie", 76.3],
                ],
            },
            "config": {
                "title": "Score Report",
                "sort_by": "score",
                "sort_ascending": False,
                "conditional_styles": [
                    {
                        "column": "score",
                        "condition": "> 90",
                        "style": {"background-color": "green", "color": "white"},
                    }
                ],
            },
        }
        resp = client.post("/api/v1/visual/table", json=request_body)
        data = resp.json()
        assert data["code"] == 0
        assert "Score Report" in data["data"]["html"]
        assert "background-color:green" in data["data"]["html"]
