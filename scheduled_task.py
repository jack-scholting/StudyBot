import datetime
import studybot

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    print("DEBUG: Periodic Task is running!")

    #TODO may need some logic to randomize study prompts.

    all_users = studybot.get_all_users()
    for user in all_users:
        print("DEBUG: User %s" % user)
        if (user.silence_end_time and user.silence_end_time <  datetime.datetime.now(user.silence_end_time.tzinfo)):
            fact = studybot.get_next_fact_to_study(user.fb_id)
            if (fact):
                studybot.send_message(user.fb_id, "Time to study!", False)
                studybot.send_message(user.fb_id, fact.question, False)
                studybot.current_user = studybot.ConvoState(user_id=user.fb_id)
                studybot.current_user.tmp_fact = fact
                studybot.set_convo_state(user.fb_id, studybot.State.WAITING_FOR_STUDY_ANSWER)
