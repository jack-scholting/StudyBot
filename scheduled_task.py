import datetime
import app

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    print("DEBUG: Periodic Task is running!")

    #TODO may need some logic to randomize study prompts.

    all_users = app.get_all_users()
    for user in all_users:
        print("DEBUG: User %s" % user)
        if (user.silence_end_time and user.silence_end_time <  datetime.datetime.now(user.silence_end_time.tzinfo)):
            fact = app.get_next_fact_to_study(user.fb_id)
            if (fact):
                app.send_message(user.fb_id, "Time to study!", False)
                app.send_message(user.fb_id, fact.question, False)
                app.current_user = app.ConvoState(user_id=user.fb_id)
                app.current_user.tmp_fact = fact
                app.set_convo_state(user.fb_id, app.State.WAITING_FOR_STUDY_ANSWER)
