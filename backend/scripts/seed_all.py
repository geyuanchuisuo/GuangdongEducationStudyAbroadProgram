"""一键种子数据编排（v6.11.39）：空库自动注入 / --force 清库重建。

统一入口，按顺序执行完整种子链：
  1. seed_data            —— drop_all + create_all 全量业务种子（含政策/项目/账号）
  2. seed_cs_faq          —— 客服 FAQ（按 question upsert）
  3. seed_supplement      —— 数据缺口补充（只填 NULL，幂等）
  4. seed_owner_rebalance —— 客户归属重分配（测试账号满屏真实数据）
  5. seed_notifications   —— 管理层通知补充

用法：
  空库自动注入（启动流程调用，已有数据不动）：python -m scripts.seed_all
  清库重建（drop_all 后全量重注）：           python -m scripts.seed_all --force

接入点（自动注入，均为空库判定，不会覆盖已有数据）：
  - docker-compose.yml edu-backend 启动命令（每次容器拉起自动执行）
  - start-project.bat [5/6]（本地一键启动自动执行）
"""
import asyncio
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


async def _db_has_data() -> bool:
    """空库判定：sys_user 有行即视为已注入过；表不存在（1146）视为空库。

    compose 冷启动时 seed_all 先于 uvicorn 建表执行，sys_user 尚未创建，
    直接查询会抛 (1146, "Table ... doesn't exist") 导致自动注入整链失败；
    此处将「表不存在」归一为空库语义，后续 seed_data 会 drop_all+create_all 自建表。
    """
    from sqlalchemy import func, select

    from app.database import async_session_factory
    from app.models.user import User

    try:
        async with async_session_factory() as session:
            n = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
        return n > 0
    except Exception as exc:
        msg = str(exc)
        if "1146" in msg or "doesn't exist" in msg:
            return False
        raise


def _run(label: str, cmd: list[str], env: dict | None = None) -> None:
    print(f"[seed-all] {label} ...", flush=True)
    r = subprocess.run(cmd, cwd=str(BACKEND_DIR), env=env)
    if r.returncode != 0:
        print(f"[seed-all] ❌ {label} 失败（exit {r.returncode}）", flush=True)
        sys.exit(1)


def _supplement_env() -> dict:
    """缺口补充脚本用 pymysql 直连：容器内运行时把 DATABASE_URL 解析为 SEED_MYSQL_* 传入。"""
    env = dict(os.environ)
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url:
        try:
            from sqlalchemy import make_url

            u = make_url(db_url)
            env.setdefault("SEED_MYSQL_HOST", u.host or "127.0.0.1")
            env.setdefault("SEED_MYSQL_PORT", str(u.port or 3306))
            env.setdefault("SEED_MYSQL_USER", u.username or "root")
            env.setdefault("SEED_MYSQL_PASSWORD", u.password or "")
            env.setdefault("SEED_MYSQL_DB", u.database or "GuangdongEducationStudyAbroadProgram")
        except Exception:
            pass
    return env


def main() -> None:
    force = "--force" in sys.argv
    has = asyncio.run(_db_has_data())
    if has and not force:
        print("[seed-all] 数据库已有数据，跳过自动注入（清空重建请运行：python -m scripts.seed_all --force）", flush=True)
        return
    print("[seed-all] 开始注入种子数据" + ("（--force 清库重建）" if force else "（检测到空库）"), flush=True)

    py = sys.executable
    _run("全量业务种子 seed_data（drop_all+create_all）", [py, "-m", "scripts.seed_data"])
    _run("客服 FAQ 种子", [py, "-m", "scripts.seed_cs_faq"])
    _run("数据缺口补充", [py, str(BACKEND_DIR / "scripts" / "seed_supplement_v6_11_13.py")], env=_supplement_env())
    _run("客户归属重分配", [py, "-m", "scripts.seed_owner_rebalance_v6_11_22"])
    _run("管理层通知补充", [py, "-m", "scripts.seed_notifications_v6_11_35"])
    print("[seed-all] ✅ 种子数据编排完成", flush=True)


if __name__ == "__main__":
    main()
