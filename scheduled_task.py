import datetime
import app

#===============================================================================
# Helper Routines
#===============================================================================
def get_all_users():
    #TODO implement
    return []


def get_next_fact(user):
    #TODO implement
    pass

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    print("DEBUG: Periodic Task is running!")

    app.send_message(1694355543971879, "Testing push message!", False)

    all_users = get_all_users()
    for user in all_users:
        if (user.silence_end_time < datetime.datetime.now()):
            next_fact = get_next_fact(user)
            if (next_fact):
                pass #TODO - start dialog with user to study fact
