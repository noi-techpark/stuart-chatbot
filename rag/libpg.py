# SPDX-FileCopyrightText: 2024 NOI Techpark <digital@noi.bz.it>
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import sys
import json
from typing import List, Dict

import psycopg2
import psycopg2.extras


def open_cursor() -> psycopg2.extras.DictCursor:
    try:
        file = open("secrets_pg.json", "r")
        conn_parameters = json.load(file)
        file.close()
    except FileNotFoundError:
        print("ERROR: open_cursor(): cannot read credentials file.")
        sys.exit(1)
    try:
        conn = psycopg2.connect("host='%s' port='%s' dbname='%s' user='%s' password='%s' connect_timeout='%s'" %
                                (
                                    conn_parameters["host"],
                                    conn_parameters["port"],
                                    conn_parameters["dbname"],
                                    conn_parameters["user"],
                                    conn_parameters["password"],
                                    conn_parameters["connect_timeout"]
                                ))
    except psycopg2.OperationalError as e:
        print("ERROR: open_cursor(): cannot open database connection:\n%s" % str(e))
        sys.exit(1)
    return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)


def close_cursor(cursor: psycopg2.extras.DictCursor) -> None:
    connection = cursor.connection
    cursor.close()
    connection.close()


def select_one(cursor: psycopg2.extras.DictCursor, query: str, args: List[str]) -> Dict[str, any]:
    try:
        cursor.execute(query, args)
        res = cursor.fetchone()
    except psycopg2.OperationalError as e:
        print("ERROR: select_one(): database error:\n%s" % str(e))
        sys.exit(1)
    return res


def select_all(cursor: psycopg2.extras.DictCursor, query: str, args: List[str]) -> List[Dict[str, any]]:
    try:
        cursor.execute(query, args)
        res = cursor.fetchall()
    except psycopg2.OperationalError as e:
        print("ERROR: select_all(): database error:\n%s" % str(e))
        sys.exit(1)
    return res


def execute(cursor: psycopg2.extras.DictCursor, query: str, args: List[str]) -> None:
    try:
        cursor.execute(query, args)
    except psycopg2.OperationalError as e:
        print("ERROR: execute(): database error:\n%s" % str(e))
        sys.exit(1)
    return
