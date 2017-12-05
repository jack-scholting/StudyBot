import datetime

#===============================================================================
# Helper Routines
#===============================================================================
def get_all_users():
    #TODO implement
    return []


def get_silence_date(user):
    #TODO implement
    pass


def after_silence_date(silence_date):
    now = datetime.datetime.now()
    #TODO implement
    pass

def get_next_fact(user):
    #TODO implement
    pass

#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    print("DEBUG: Periodic Task is running!")

    all_users = get_all_users()
    for user in all_users:
        silence_date = get_silence_date(user)
        if (after_silence_date(silence_date)):
            next_fact = get_next_fact(user)
            if (next_fact):
                pass #TODO - start dialog with user to study fact
