"""数据库连接模块 — PyMySQL 连接管理

提供线程安全的数据库连接获取与释放。
所有 SQL 通过参数化查询执行，禁止拼接字符串。
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

import pymysql

from config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME, DB_CHARSET

# 线程局部存储：每个线程持有一个连接
_local = threading.local()


def _create_connection() -> pymysql.Connection:
    """创建新的数据库连接。"""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def get_connection() -> pymysql.Connection:
    """获取当前线程的数据库连接。

    如果不存在或已断开，则自动创建新连接。
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _create_connection()
        _local.conn = conn
        return conn
    try:
        conn.ping(reconnect=True)
    except Exception:
        conn = _create_connection()
        _local.conn = conn
    return conn


@contextmanager
def transaction():
    """数据库事务上下文管理器。

    用法：
        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
            # 自动 commit，异常时自动 rollback

    Yields:
        pymysql.Connection: 数据库连接对象
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def execute_query(
    sql: str, params: tuple | None = None, fetch_one: bool = False
) -> list[dict[str, Any]] | dict[str, Any] | None:
    """执行查询并返回结果。

    Args:
        sql: SQL 语句（使用 %s 占位符）
        params: 参数元组
        fetch_one: True 返回单行 dict，False 返回列表

    Returns:
        查询结果
    """
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        if fetch_one:
            return cursor.fetchone()
        return cursor.fetchall()


def execute_update(sql: str, params: tuple | None = None) -> int:
    """执行写操作（INSERT/UPDATE/DELETE）。

    Args:
        sql: SQL 语句
        params: 参数元组

    Returns:
        影响行数
    """
    with transaction() as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(sql, params)
        return affected


def execute_insert(sql: str, params: tuple | None = None) -> int:
    """执行 INSERT 并返回自增 ID。

    Args:
        sql: INSERT 语句
        params: 参数元组

    Returns:
        新插入行的自增 ID
    """
    with transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.lastrowid
