"""
Tests for app.services.progress_store
"""
from app.services import progress_store as ps


class TestProgressStore:
    """progress_store CRUD 操作测试"""

    def test_get_returns_default_when_empty(self, patch_progress_store):
        """无记录时返回默认进度"""
        data = ps.get("test", "key1")
        assert data["status"] == "not_started"
        assert data["progress"] == 0

    def test_init_creates_running_task(self, patch_progress_store):
        """init 创建 running 状态的任务"""
        ps.init("gen", "batch1", total=10, first_log="开始")
        data = ps.get("gen", "batch1")
        assert data["status"] == "running"
        assert data["total"] == 10
        assert data["logs"] == ["开始"]

    def test_update_merges_fields(self, patch_progress_store):
        """update 增量更新字段"""
        ps.init("gen", "b1", total=5, first_log="go")
        ps.update("gen", "b1", completed=3, progress=60)
        data = ps.get("gen", "b1")
        assert data["completed"] == 3
        assert data["progress"] == 60
        assert data["status"] == "running"  # 未改变

    def test_append_log(self, patch_progress_store):
        """append_log 追加日志"""
        ps.init("x", "k", total=1, first_log="L1")
        ps.append_log("x", "k", "L2")
        data = ps.get("x", "k")
        assert data["logs"] == ["L1", "L2"]

    def test_logs_truncated_to_max(self, patch_progress_store):
        """日志超过 MAX_LOGS 时截断"""
        ps.init("x", "k", total=1, first_log="L0")
        for i in range(1, 30):
            ps.append_log("x", "k", f"L{i}")
        data = ps.get("x", "k")
        assert len(data["logs"]) <= ps.MAX_LOGS

    def test_finish_marks_completed(self, patch_progress_store):
        """finish 标记任务完成"""
        ps.init("c", "k", total=5, first_log="start")
        ps.finish("c", "k", completed=4, failed=1, final_log="done")
        data = ps.get("c", "k")
        assert data["status"] == "completed"
        assert data["progress"] == 100
        assert data["completed"] == 4
        assert data["failed"] == 1
        assert "done" in data["logs"]

    def test_fail_marks_error(self, patch_progress_store):
        """fail 标记任务失败"""
        ps.init("c", "k", total=5, first_log="start")
        ps.fail("c", "k", "boom")
        data = ps.get("c", "k")
        assert data["status"] == "error"
        assert "boom" in data["logs"]

    def test_is_running(self, patch_progress_store):
        """is_running 正确判断"""
        assert ps.is_running("a", "b") is False
        ps.init("a", "b", total=1, first_log="go")
        assert ps.is_running("a", "b") is True
        ps.finish("a", "b", 1, 0, "ok")
        assert ps.is_running("a", "b") is False

    def test_extra_fields_persisted(self, patch_progress_store):
        """extra 字段（非基础字段）能正确存取"""
        ps.init("e", "k", total=1, first_log="go", per_image={"img1": "ok"})
        data = ps.get("e", "k")
        assert data["per_image"] == {"img1": "ok"}

    def test_cache_cleared_reads_from_db(self, patch_progress_store):
        """清除缓存后仍能从 DB 读取"""
        ps.init("db", "k", total=3, first_log="hi")
        ps._cache.clear()  # 模拟重启
        data = ps.get("db", "k")
        assert data["status"] == "running"
        assert data["total"] == 3
