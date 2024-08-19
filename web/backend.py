import sys
import uuid
from flask import Flask, jsonify, request, abort

from libsql import *

import os

def main():

    sql_init()

    preshared_secret = os.environ.get('PRESHARED_SECRET')

    app = Flask("stuart", static_folder="static", static_url_path="/")

    '''
    frontend: entry point, create a new session and redirect to it
    '''
    @app.route("/")
    def new_session():
        unique_id = str(uuid.uuid4())
        sql_add_session(unique_id)
        return app.redirect("/session?uuid=%s" % unique_id, code=302)

    '''
    frontend: serve the page if the session is valid
    (otherwise redirect to /)
    '''
    @app.route("/session")
    def session():
        unique_id = str(request.args.get('uuid'))
        if sql_get_state(unique_id) is None:
            return app.redirect("/", code=302)
        return app.send_static_file("index.html")

    '''
    frontend: receive a new question, if the session is valid and
    in the correct state, store the question in the DB and update state
    '''
    @app.route("/add_question", methods=["POST"])
    def add_question():
        unique_id = str(request.form.get("uuid"))
        question = (str(request.form.get("question"))).strip()
        if sql_add_question(unique_id, question):
            return jsonify({"msg": "OK"})
        else:
            return jsonify({"msg": "Error: invalid session"})

    '''
    frontend: get state for given session
    '''
    @app.route("/get_state")
    def get_state():
        unique_id = str(request.args.get("uuid"))
        state = sql_get_state(unique_id)
        if state is None:
            return jsonify({"msg": "Error: invalid session"})
        else:
            return jsonify({"msg": "OK", "state": state})

    '''
    frontend: get state and conversation for given session
    '''
    @app.route("/get_state_and_conversation")
    def get_state_and_conversation():
        unique_id = str(request.args.get("uuid"))
        res = sql_get_state_and_conversation(unique_id)
        if res is None:
            return jsonify({"msg": "Error: invalid session"})
        else:
            return jsonify(res)

    '''
    frontend: check heartbeat from inference server
    '''
    @app.route("/get_heartbeat")
    def get_heartbeat():
        age = sql_get_heartbeat()
        return jsonify({"age": age})

    '''
    inference server: if preshared secret matches, set heartbeat
    '''
    @app.route("/heartbeat")
    def heartbeat():
        secret = str(request.args.get("secret"))
        if secret != preshared_secret:
            abort(403)
        sql_heartbeat()
        return jsonify({"msg": "OK"})

    '''
    inference server: if preshared secret matches and a session
    has a pending question, claim it
    '''
    @app.route("/claim_job")
    def claim_job():
        secret = str(request.args.get("secret"))
        if secret != preshared_secret:
            abort(403)
        ret = sql_claim_job()
        return jsonify(ret)

    '''
    inference server: if preshared secret matches, accept
    job update
    '''
    @app.route("/finish_job", methods=["POST"])
    def finish_job():
        secret = str(request.form.get("secret"))
        if secret != preshared_secret:
            abort(403)
        unique_id = str(request.form.get("uuid"))
        conversation_llm = str(request.form.get("conversation_llm"))
        conversation = str(request.form.get("conversation"))
        source = str(request.form.get("source"))
        sql_finish_job(unique_id, conversation_llm, conversation, source)
        return jsonify({"msg": "OK"})

    '''
    watchdog: if preshared secret matches, return the number
    of sessions for each state
    '''
    @app.route("/get_state_count")
    def get_state_count():
        secret = str(request.args.get("secret"))
        if secret != preshared_secret:
            abort(403)
        ret = sql_get_state_count()
        return jsonify(ret)

    '''
        watchdog: if preshared secret matches, return the
        age of the latest session in seconds for each state
        '''
    @app.route("/get_state_latest_age")
    def get_state_latest_age():
        secret = str(request.args.get("secret"))
        if secret != preshared_secret:
            abort(403)
        ret = sql_get_state_latest_age()
        return jsonify(ret)

    if __name__ == '__main__':
        bind_ip = os.environ.get('BIND_IP')
        bind_port = os.environ.get('BIND_PORT')
        app.run(host=bind_ip, port=bind_port)


main()
