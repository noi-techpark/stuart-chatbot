"use strict";

(() => {

    // -------------------------------------------------------------------------
    // We don't need no framework.
    // We don't need no thought control.
    // Hey! Teachers! Leave them devs alone!

    const $ = document.querySelector.bind(document);
    const enable = id => $("#" + id).disabled = false;
    const disable = id => $("#" + id).disabled = true;
    const make_params = obj => {
        const params = new URLSearchParams();
        for (let key in obj) {
            params.append(key, obj[key]);
        }
        return params;
    };
    const fatal_exit = msg => {
        alert(msg + "\n\nConfirm to open a fresh session.");
        document.location.href = "/";
    }

    // -------------------------------------------------------------------------
    // Initialization.

    const unique_id= new URL(window.location.href).searchParams.get("uuid");
    if (!unique_id.match(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/)) {
        fatal_exit("Stuart frontend error: cannot get my own UUID.");
    }
    $("#uuid").href = window.location.href;
    $("#uuid").textContent = unique_id;

    const STATE_UNKNOWN = 0;
    const STATE_WAIT_FOR_QUESTION = 1;
    const STATE_QUESTION_SENT = 2;
    const STATE_QUESTION_QUEUED = 3;
    const STATE_PROCESSING_QUESTION = 4;

    let state = STATE_UNKNOWN;


    // -------------------------------------------------------------------------
    // Refresh according to saved state in the backend.

    const refresh = () => {
        fetch("/get_state_and_conversation?" + make_params({"uuid": unique_id}))
            .then( res => res.json())
            .then(data => {
                if (data?.msg !== "OK") {
                    fatal_exit("Stuart error: invalid session (get_state_and_conversation).");
                }
                let conversation = data?.conversation;
                let source = data?.source
                if (!Array.isArray(conversation)) {
                    conversation = [];
                }
                let is_question = true;
                $("#conversation").innerHTML = "";
                let source_ix = 0;
                conversation.forEach( part => {
                    let p = document.createElement("p");
                    if (is_question) {
                        p.classList.add("conversation_question");
                    } else {
                        p.classList.add("conversation_answer");
                    }
                    p.textContent = part;
                    $("#conversation").appendChild(p);
                    if (!is_question) {
                        let s = document.createElement("p");
                        s.textContent = source[source_ix++];
                        s.classList.add("conversation_source");
                        $("#conversation").appendChild(s);
                    }
                    is_question = !is_question;
                });
                let this_state = String(data?.state);
                switch(this_state) {
                    case "wait-for-question":
                        state = STATE_WAIT_FOR_QUESTION;
                        $("#user_wait_animation").innerHTML = "&nbsp;";
                        $("#user_question").value = '';
                        enable("user_question");
                        $("#user_question").focus();
                        window.scrollTo(0, document.body.scrollHeight);
                        break;
                    case "question-queued":
                        state = STATE_QUESTION_QUEUED;
                        disable("user_question");
                        break;
                    case "processing-question":
                        state = STATE_PROCESSING_QUESTION;
                        disable("user_question");
                        break;
                }
            })
            .catch(error => {
                    fatal_exit("Stuart backend error: communication error (get_state_and_conversation).");
            });
    }

    refresh();


    // -------------------------------------------------------------------------
    // Handle state machine.

    // Handle transitions STATE_QUESTION_SENT -> STATE_QUESTION_QUEUED,
    // STATE_QUESTION_QUEUED -> STATE_PROCESSING_QUESTION and
    // STATE_PROCESSING_QUESTION -> STATE_WAIT_FOR_QUESTION;
    // this is triggered by state changes in the backend retrieved by polling.
    let poll_state = () => {
        fetch("/get_state?" + make_params({"uuid": unique_id}))
            .then( res => res.json())
            .then(data => {
                let continue_polling = false;
                if (data?.msg === "OK") {
                    let this_state = data?.state;
                    if (this_state === "question-queued") {
                        state = STATE_QUESTION_QUEUED;
                        continue_polling = true;
                    } else if (this_state === "processing-question") {
                        state = STATE_PROCESSING_QUESTION;
                        continue_polling = true;
                    } else if (this_state === "wait-for-question") {
                        state = STATE_WAIT_FOR_QUESTION;
                        refresh();
                    }
                } else {
                    fatal_exit("Stuart error: invalid session (get_state).");
                }
                if (continue_polling) {
                    setTimeout(poll_state, 1000);
                }
            })
            .catch(error => {
                    fatal_exit("Stuart backend error: communication error (get_state).");
            });
    }

    // Handle transition STATE_WAIT_FOR_QUESTION -> STATE_QUESTION_SENT;
    // this is triggered by hitting "Enter" in the #user_question textarea.
    $("#user_question").onkeydown = (event) => {
        if (state !== STATE_WAIT_FOR_QUESTION) {
            return;
        }
        if (event.key !== 'Enter' || event.shiftKey ) {
            return;
        }
        let val = $("#user_question").value.trim();
        if (val.length === 0) {
            return;
        }
        disable("user_question");
        fetch('/add_question', { method: "POST",
                                 headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                                 body: make_params({"uuid": unique_id, "question": $("#user_question").value})
                                })
            .then( res => res.json())
            .then(data => {
                if (data?.msg === "OK") {
                    state = STATE_QUESTION_SENT;
                    poll_state();
                } else {
                    fatal_exit("Stuart error: invalid session (add_question).");
                }
            })
            .catch(error => {
                    fatal_exit("Stuart backend error: communication error (add_question).");
            });

    };


    // -------------------------------------------------------------------------
    // Handle inference server status display.
    // This is independent of the state machine.

    const get_heartbeat = () => {
        fetch('/get_heartbeat')
            .then( res => res.json())
            .then(data => {
                try {
                    let age = Number(data.age)
                    if (age < 10) {
                        $("#heartbeat").innerHTML = "<span class=\"good\">up</span>";
                    } else {
                        $("#heartbeat").innerHTML = "<span class=\"bad\">down</span>";
                    }
                } catch (e) {
                    $("#heartbeat").innerHTML = "<span class=\"bad\">unknown state</span>";
                    setTimeout(get_heartbeat, 5000);
                }
                setTimeout(get_heartbeat, 5000);
            })
            .catch(error => {
                $("#heartbeat").innerHTML = "<span class=\"bad\">unknown state</span>";
                setTimeout(get_heartbeat, 5000);
            });
    }
    get_heartbeat();


    // -------------------------------------------------------------------------
    // Waiting animation.

    const waitani = () => {
        let message = "&nbsp;";
        if ([STATE_QUESTION_SENT, STATE_QUESTION_QUEUED, STATE_PROCESSING_QUESTION].includes(state)) {
            for (let i = 0; i < 40; i++) {
                if (i === 20) {
                    switch(state) {
                        case STATE_QUESTION_SENT:       message += " sending question "; break;
                        case STATE_QUESTION_QUEUED:     message += " question queued "; break;
                        case STATE_PROCESSING_QUESTION: message += " processing question "; break;
                    }
                }
                let codepoint = 0x2800 + Math.floor(0x100 * Math.random());  // braille range
                message += "&#x" + codepoint.toString(16) + ";";
            }
        }
        $("#user_wait_animation").innerHTML = message;
        setTimeout(waitani, 500);
    };
    waitani();


})();