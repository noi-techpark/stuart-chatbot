import sqlite3
import json
from typing import Optional, Dict

sql_settings = {
    "db_path": "./db/stuart.db"
}


def sql_init():
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        CREATE TABLE IF NOT EXISTS session (
          uuid TEXT,
          conversation_llm TEXT,
          conversation TEXT,
          source TEXT,
          state TEXT,
          created INT,
          modified INT,
          CHECK(state IN ('wait-for-question', 'question-queued', 'processing-question'))
        );
    ''')
    curs.execute('''
        CREATE TABLE IF NOT EXISTS heartbeat (
          modified INT
        );
    ''')
    curs.execute('''
           INSERT INTO heartbeat (modified) VALUES (STRFTIME('%s', 'now'));
       ''')

    conn.commit()
    conn.close()


def sql_add_session(unique_id: str):
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        INSERT INTO session (uuid, conversation_llm, conversation, source, state, created, modified)
          VALUES (?, '[]', '[]', '[]', 'wait-for-question', STRFTIME('%s', 'now'), STRFTIME('%s', 'now'));
    ''', [unique_id])
    conn.commit()
    conn.close()


def sql_add_question(unique_id: str, question: str) -> bool:
    success = False
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT conversation
          FROM session
          WHERE uuid = ? and state = 'wait-for-question';
    ''', [unique_id])
    res = curs.fetchone()
    if res is not None:
        conversation = json.loads(res[0])
        conversation.append(question)
        curs.execute('''
            UPDATE session
              SET conversation = ?,
                  state = 'question-queued',
                  modified = STRFTIME('%s', 'now')
              WHERE uuid = ?;
        ''', [json.dumps(conversation), unique_id])
        success = True
    conn.commit()
    conn.close()
    return success


def sql_get_state(unique_id: str) -> Optional[str]:
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT state FROM session WHERE uuid = ?;
    ''', [unique_id])
    res = curs.fetchone()
    ret = None
    if res is not None:
        ret = str(res[0])
    conn.commit()
    conn.close()
    return ret


def sql_get_state_and_conversation(unique_id: str) -> Optional[Dict]:
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT state, conversation, source FROM session WHERE uuid = ?;
    ''', [unique_id])
    res = curs.fetchone()
    ret = None
    if res is not None:
        ret = {"msg": "OK", "state": str(res[0]), "conversation": json.loads(str(res[1])), "source": json.loads(str(res[2]))}
    conn.commit()
    conn.close()
    return ret


def sql_claim_job() -> Dict:
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT uuid, conversation_llm, conversation, source FROM session
            WHERE state = 'question-queued'
            ORDER BY modified DESC LIMIT 1;
    ''')
    res = curs.fetchone()
    if res is not None:
        unique_id = res[0]
        conversation_llm = res[1]
        conversation = res[2]
        source = res[3]
        ret = {"uuid": unique_id, "conversation_llm": conversation_llm, "conversation": conversation, "source": source}
        curs.execute('''
            UPDATE session
              SET state = 'processing-question',
                  modified = STRFTIME('%s', 'now')
              WHERE uuid = ?;
        ''', [unique_id])
    else:
        ret = {}
    conn.commit()
    conn.close()
    return ret


def sql_get_pending_count() -> Dict:
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT count(*) as cnt FROM session
            WHERE state = 'question-queued' or state = 'processing-question';
    ''')
    res = curs.fetchone()
    ret = {"count": res[0]}
    conn.commit()
    conn.close()
    return ret


def sql_finish_job(unique_id: str, conversation_llm: str, conversation: str, source: str):
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        UPDATE session
          SET state = 'wait-for-question',
              modified = STRFTIME('%s', 'now'),
              conversation_llm = ?,
              conversation = ?,
              source = ?
          WHERE uuid = ?;
    ''', [conversation_llm, conversation, source, unique_id])
    conn.commit()
    conn.close()
    print("success finished job for uuid = %s" %  unique_id)


def sql_heartbeat():
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        UPDATE heartbeat set modified = STRFTIME('%s', 'now');
    ''')
    conn.commit()
    conn.close()
    return


def sql_get_heartbeat():
    conn = sqlite3.connect(sql_settings.get("db_path"))
    curs = conn.cursor()
    curs.execute('''
        SELECT STRFTIME('%s', 'now') - modified FROM heartbeat;
    ''')
    res = curs.fetchone()
    if res is None:
        age = 1e9
    else:
        age = res[0]
    conn.commit()
    conn.close()
    return age
