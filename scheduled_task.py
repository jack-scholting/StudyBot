import datetime
import app

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    print("DEBUG: Periodic Task is running!")

    #TODO may need some logic to randomize study prompts.

    all_users = get_all_users()
    for user in all_users:
        if (user.silence_end_time < datetime.datetime.now()):
            fact = get_next_fact_to_study(user.id)
            if (fact):
                app.send_message(user.fb_id, "Time to study!", False)
                app.send_message(user.fb_id, fact.question, False)
                app.set_convo_state(sender_id, State.WAITING_FOR_STUDY_ANSWER)
