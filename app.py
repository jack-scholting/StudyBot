from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from collections import namedtuple

import json
import requests
import os
import enum
import redis

# Create the Flask application instance.
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Get Redis Cache
cache = redis.from_url(os.environ.get("REDIS_URL"))

#===============================================================================
# DB Classes
#===============================================================================
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    fb_id = db.Column(db.String, unique=True)
    facts = db.relationship('Fact', lazy='select', backref=db.backref('users', lazy='joined'))

    def __init__(self, fb_id):
        self.fb_id = fb_id

    def __repr__(self):
        return '<FB ID %r>' % self.fb_id

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'fb_id': self.fb_id,
            'facts': self.serialize_one2many
        }

    @property
    def serialize_one2many(self):
       """
       Return object's relations in easily serializeable format.
       NB! Calls many2many's serialize property.
       """
       return [item.serialize for item in self.facts]

class Fact(db.Model):
    __tablename__ = 'facts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    question = db.Column(db.String, unique=True)
    answer = db.Column(db.String, nullable=False)
    confidence = db.Column(db.Integer)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.Index('user_id_question', 'user_id', db.text("lower(question)")),
        db.CheckConstraint('confidence >= 0 AND confidence <=5', name='check_confidence')
    )

    def __repr__(self):
        return '<FB ID - Fact: %r - %r: %r>' % self.fb_id, self.question, self.answer

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'question': self.question,
            'answer': self.answer,
            'confidence': self.confidence,
            'last_seen': self.last_seen
        }


#===============================================================================
# General Classes
#===============================================================================
class ConvoState:
    def __init__(self, user_id, state=None):
        self.user_id = user_id
        self.tmp_fact = Fact(user_id=user_id)
        self.state = State.DEFAULT if state is None else state

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'user_id': self.user_id,
            'tmp_fact': self.tmp_fact.serialize,
            'state': self.state.value
        }


#===============================================================================
# Constants
#===============================================================================
# See https://developers.facebook.com/docs/messenger-platform/reference/send-api
SEND_API_URL = "https://graph.facebook.com/v2.6/me/messages"

RANDOM_PHRASES = [
    "Hey %s, how the heck are ya? Me, you ask? I'm feeling a little blue. :)",
    "Studying again %s? Look at you! We gotta future Rhodes scholar here!",
    "You want to study right now, %s? Nerd Alert! Nerds are so in right now!"
]

"""
Note: This is a trade-off between "precision" and "recall" as discussed here:
https://wit.ai/docs/recipes#which-confidence-threshold-should-i-use
"""
MIN_CONFIDENCE_THRESHOLD = 0.7

# Expire cached entries after 5 minutes
CACHE_EXPIRATION_IN_SECONDS = 300

"""
The following states are used to create a conversation flow.
"""
class State(enum.Enum):
    DEFAULT = 0
    WAITING_FOR_FACT_QUESTION = 1
    WAITING_FOR_FACT_ANSWER = 2


#===============================================================================
# Global Data
#===============================================================================
current_user = None


#===============================================================================
# Flask Routines
#===============================================================================
"""
GET requests are used for authentication.
Handle GET requests by verifying Facebook is sending the correct token that we
setup in the facebook app.
"""
@app.route('/', methods=['GET'])
def handle_verification():
    print("DEBUG: Handling Verification.")
    if request.args.get('hub.verify_token', '') == get_verif_token():
        print("DEBUG: Verification successful!")
        return request.args.get('hub.challenge', '')
    else:
        print("DEBUG: Verification failed!")
        return 'Error, wrong validation token'

"""
POST requests are for communication.
Handle POST requests by interpretting the user message, then sending the
appropriate response.
"""
@app.route('/', methods=['POST'])
def handle_messages():
    print("DEBUG: Handling Messages")
    payload = request.get_json()
    print(payload)

    """
    Note: For more information on what is being processed here, see the webhook
    documentation at https://developers.facebook.com/docs/messenger-platform/webhook
    """
    if (payload):
        # The webhook event should only be coming from a Page subscription.
        if (payload.get("object") == "page"):
            # The "entry" is an array and could contain multiple webhook events.
            for entry in payload["entry"]:
                # The "messaging" event occurs when a message is sent to our page.
                for messaging_event in entry["messaging"]:
                    if (messaging_event.get("postback")):
                        #TODO - handle welcome message per:
                        #https://developers.facebook.com/docs/messenger-platform/discovery/welcome-screen
                        pass

                    if (messaging_event.get("message")):
                        """
                        Note: The ID is a page-scoped ID (PSID). It is a unique
                        identifier for a given person interacting with a given page.
                        """
                        sender_id = messaging_event["sender"]["id"]
                        if messaging_event["message"].get("text"):
                            sender_msg = messaging_event["message"]["text"].encode('unicode_escape')
                        else:
                            sender_msg = "Not text"
                        if messaging_event["message"].get("nlp"):
                            nlp = messaging_event["message"]["nlp"]
                        else:
                            nlp = {"entities": {}}

                        print("DEBUG: Incoming from %s: %s" % (sender_id, sender_msg))
                        bot_msg = ""

                        change_typing_indicator(enabled=True, user_id=sender_id)

                        if (is_first_time_user(sender_id)):
                            create_user(sender_id)
                            send_welcome_message(sender_id)
                            set_convo_state(sender_id, State.DEFAULT)
                        else:
                            restore_convo_state(sender_id)
                            print("DEBUG: current_user")
                            print(current_user.serialize)

                            convo_state = current_user.state

                            print("DEBUG: Conversation State: " + convo_state.name)

                            if (convo_state == State.DEFAULT):
                                if (msg_contains_greeting(nlp["entities"], MIN_CONFIDENCE_THRESHOLD)):
                                    send_greeting_message(sender_id)
                                else:

                                    strongest_intent = get_strongest_intent(nlp["entities"], MIN_CONFIDENCE_THRESHOLD)
                                    print("DEBUG: NLP intent: " + strongest_intent)

                                    if (strongest_intent == "add_fact"):
                                        bot_msg = "Ok, let's add that new fact. What is the question?"
                                        set_convo_state(sender_id, State.WAITING_FOR_FACT_QUESTION)
                                    elif (strongest_intent == "change_fact"):
                                        #TODO - display facts using some sort of interactive list.
                                        bot_msg = "Ok, which fact do you want to change?"
                                    elif (strongest_intent == "silence_studying"):
                                        #TODO - add NLP support for finding dates and times.
                                        bot_msg = "Ok, you want to silence study notifications until xx.\nIs that right?"
                                    elif (strongest_intent == "view_facts"):
                                        #TODO - display facts using some sort of interactive list.
                                        bot_msg = "Ok, here are the facts we have.\n"
                                        bot_msg = bot_msg + str(get_user_facts(sender_id))
                                    elif (strongest_intent == "delete_fact"):
                                        #TODO - display facts using some sort of interactive list.
                                        bot_msg = "Ok, which fact do you want to delete?"
                                    elif (strongest_intent == "study_next_fact"):
                                        #TODO - start study flow
                                        pass
                                    elif (strongest_intent == "default_intent"):
                                        #TODO - provide user some suggested actions to help them.
                                        bot_msg = "I'm not sure what you mean."
                                        set_convo_state(sender_id, current_user.state)

                            elif (convo_state == State.WAITING_FOR_FACT_QUESTION):
                                current_user.tmp_fact.user_id = current_user.user_id
                                current_user.tmp_fact.question = sender_msg.decode("unicode_escape")
                                set_convo_state(sender_id, State.WAITING_FOR_FACT_ANSWER)
                                bot_msg = "Thanks, what's the answer to that question?"

                            elif (convo_state == State.WAITING_FOR_FACT_ANSWER):
                                current_user.tmp_fact.answer = sender_msg.decode("unicode_escape")
                                create_new_fact(current_user.tmp_fact)
                                bot_msg = "Ok, I added the following question and answer:\n"
                                bot_msg += "Question: %s\n" % current_user.tmp_fact.question
                                bot_msg += "Answer: %s" % current_user.tmp_fact.answer
                                set_convo_state(sender_id, State.DEFAULT)

                            send_message(sender_id, bot_msg, is_response=True)

                        change_typing_indicator(enabled=False, user_id=sender_id)
        else:
            print("DEBUG: Error: Event object is not a page.")
    else:
        print("DEBUG: Error: POST payload was empty.")

    """
    Per the documentation, the webhook should always return "200 OK", otherwise
    the webhook may be unsubscribed from the Messenger Platform.
    """
    return ("ok", 200)


# ===============================================================================
# Helper Routines
# ===============================================================================
def restore_convo_state(sender_id):
    user_data = cache.get(sender_id)
    if not user_data:
        print("DEBUG: Cache miss. Building convo state.")
        user_data = get_user(sender_id)
        user_data = ConvoState(user_data.id, State.DEFAULT)
    else:
        print("DEBUG: Cache hit. Using cached convo state.")
        tmp = json.loads(user_data)
        user_data = ConvoState(tmp["user_id"], State(tmp["state"]))
        user_data.tmp_fact = Fact()
        user_data.tmp_fact.id = tmp["tmp_fact"]["id"]
        user_data.tmp_fact.user_id = tmp["tmp_fact"]["user_id"]
        user_data.tmp_fact.question = tmp["tmp_fact"]["question"]
        user_data.tmp_fact.answer = tmp["tmp_fact"]["answer"]
        user_data.tmp_fact.confidence = tmp["tmp_fact"]["confidence"]
        user_data.tmp_fact.last_seen = tmp["tmp_fact"]["last_seen"]
    set_user(user_data)


def set_convo_state(sender_id, new_state):
    global current_user
    current_user.state = new_state
    set_user(current_user)
    print("DEBUG: Cache set.")
    cache.set(sender_id, json.dumps(current_user.serialize))
    cache.expire(sender_id, CACHE_EXPIRATION_IN_SECONDS)


def set_user(user_data):
    print("DEBUG: Updating current_user.")
    global current_user

    current_user = user_data
    print(current_user.serialize)


def get_next_fact_to_study(user_id):
    #TODO - pull fact from database according to SR algorithm.
    pass


def msg_contains_greeting(nlp_entities, min_conf_threshold):
    return_val = False

    if (nlp_entities.get('greetings')):
        if(nlp_entities['greetings'][0]['confidence'] > min_conf_threshold):
            return_val = True

    return(return_val)


def get_strongest_intent(nlp_entities, min_conf_threshold):
    strongest_intent = "default_intent"
    highest_confidence_seen = min_conf_threshold

    for nlp_entity in nlp_entities:
        if (nlp_entity == 'intent'):
            confidence = nlp_entities[nlp_entity][0]['confidence']
            if (confidence > highest_confidence_seen):
                highest_confidence_seen = confidence
                strongest_intent = nlp_entities[nlp_entity][0]['value']

    return(strongest_intent)


def get_verif_token():
    """
    This is a secret token we provide Facebook so we can verify the request is
    actually coming from Facebook.
    It was set in our Heroku environment using the following command:
       heroku config:add VERIFY_TOKEN=your_token_here
    """
    return(os.environ["VERIFY_TOKEN"])


def get_page_access_token():
    """
    This PAT (Page Access Token) is used to authenticate our requests/responses.
    It was generated during the setup of our Facebook page and Facebook app.
    It was set in our Heroku environment using the following command:
       heroku config:add PAGE_ACCESS_TOKEN=your_token_here
    """
    return(os.environ["PAGE_ACCESS_TOKEN"])


def change_typing_indicator(enabled, user_id):
    if(enabled):
        action = "typing_on"
    else:
        action = "typing_off"

    headers = {
        'Content-type': 'application/json'
    }
    params = {
        "access_token": get_page_access_token()
    }
    data = json.dumps({
        "recipient": {"id": user_id},
        "sender_action": action
    })

    r = requests.post(url=SEND_API_URL, params=params, data=data, headers=headers)

    # Check the returned status code of the POST.
    if r.status_code != requests.codes.ok:
        print("DEBUG: " + r.text)


def send_message(user_id, msg_text, is_response):
    """
    Send the message msg_text to recipient.
    """
    if (is_response):
        msg_type = "RESPONSE"
    else:
        msg_type = "NON_PROMOTIONAL_SUBSCRIPTION"

    headers = {
        'Content-type': 'application/json'
    }
    params = {
        "access_token": get_page_access_token()
    }
    data = json.dumps({
        "message_type": msg_type,
        "recipient": {"id": user_id},
        "message": {"text": msg_text}
    })

    r = requests.post(url=SEND_API_URL, params=params, data=data, headers=headers)

    # Check the returned status code of the POST.
    if r.status_code != requests.codes.ok:
        print("DEBUG: " + r.text)


"""
Explaination at https://developers.facebook.com/docs/messenger-platform/identity/user-profile
"""
def get_users_firstname(user_id):
    url = "https://graph.facebook.com/v2.6/" + str(user_id)

    params = {
        "access_token": get_page_access_token(),
        "fields" : "first_name"
    }

    r = requests.get(url=url, params=params)
    json_response = json.loads(r.text)
    return (json_response["first_name"])


def get_user(user_id):
    return User.query.filter_by(fb_id=user_id).one_or_none()


def is_first_time_user(sender_id):
    print("DEBUG: Checking if user %s exists" % sender_id)
    current_user = get_user(sender_id)
    print("DEBUG: User %r" % current_user)
    return True if (current_user is None) else False


def send_welcome_message(sender_id):
    firstname = get_users_firstname(sender_id)
    msg = "Hello "+firstname+", I'm StudyBot. Nice to meet you!"
    send_message(sender_id, msg, is_response=True)
    #TODO Add instructions for the user.


def send_greeting_message(sender_id):
    from random import randint
    phrase = RANDOM_PHRASES[randint(0, len(RANDOM_PHRASES)-1)]
    msg = phrase % get_users_firstname(sender_id)
    send_message(sender_id, msg, is_response=True)


def create_user(sender_id):
    new_user = User(fb_id=sender_id)
    db.session.add(new_user)
    db.session.commit()


def create_new_fact(new_fact_record):
    return_msg = "Fact Added Successfully"
    try:
        db.session.add(new_fact_record)
        db.session.commit()
    except:
        return_msg = "Failed to add fact. Did you add this fact already?"
    return return_msg


def get_user_facts(sender_id):
    facts = get_user(sender_id).facts
    return_msg = ""
    for fact in facts:
        return_msg += "Question: %s\n" % fact.question
        return_msg += "Answer: %s\n" % fact.answer
        return_msg += "Confidence: %s\n" % fact.confidence
        return_msg += "Last Seen: %s\n\n" % "{:%B %d, %Y}".format(fact.last_seen)
    return return_msg


def delete_fact(sender_id, fact):
    user = User.query.filter_by(fb_id=sender_id)
    fact_record = Fact(user_id=user.id, fact=fact)
    db.session.delete(fact_record)
    db.session.commit()


# ===============================================================================
# Main
# ===============================================================================
if __name__ == '__main__':
    """
    Start the Flask app, the app will start listening for requests on port 5000.
    """
    app.run()
