from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import requests
import os

# Create the Flask application instance.
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


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
    fact = db.Column(db.String, unique=True)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('user_id', 'fact', name='user_id_fact'),
    )

    def __repr__(self):
        return '<FB ID - Fact: %r - %r>' % self.fb_id, self.fact

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'fact': self.fact,
            'last_seen': self.last_seen
        }

#===============================================================================
# Global Data
#===============================================================================
# See https://developers.facebook.com/docs/messenger-platform/reference/send-api
SEND_API_URL = "https://graph.facebook.com/v2.6/me/messages"

RANDOM_PHRASES = [
    "Hey %s, how the heck are ya? Me, you ask? I'm feeling a little blue. :)",
    "Studying again %s? Look at you! We gotta future Rhodes scholar here!",
    "You want to study right now, %s? Nerd Alert! Nerds are so in right now!"
]

"""
Note: This is a trade-off between "precision" and "recall"
as discussed here:
https://wit.ai/docs/recipes#which-confidence-threshold-should-i-use
"""
MIN_CONFIDENCE_THRESHOLD = 0.6

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
                        message = messaging_event["message"]["text"].encode('unicode_escape')
                        nlp = messaging_event["message"]["nlp"]
                        print("DEBUG: Incoming from %s: %s" % (sender_id, message))

                        change_typing_indicator(enabled=True, user_id=sender_id)

                        if (is_first_time_user(sender_id)):
                            create_user(sender_id)
                            send_welcome_message(sender_id)

                        if (msg_contains_greeting(nlp["entities"], MIN_CONFIDENCE_THRESHOLD)):
                            send_greeting_message(sender_id)

                        strongest_intent = get_strongest_intent(nlp["entities"], MIN_CONFIDENCE_THRESHOLD)
                        print("DEBUG: NLP intent: " + strongest_intent)

                        if (strongest_intent == "default_intent"):
                            pass
                        elif (strongest_intent == "save_fact"):
                            pass
                        #TODO - handle additional intents


                        #TODO we will need to add some handling for modes, for conversation flows.

                        #TODO - consider adding a message type based on what we are sending.
                        #   https://developers.facebook.com/docs/messenger-platform/send-messages/#messaging_types

                        #TODO - temporary code, just echos the message.
                        firstname = get_users_firstname(sender_id)
                        msg_text = "Hello " + firstname + " : " + message

                        send_message(sender_id, msg_text)
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

#===============================================================================
# Helper Routines
#===============================================================================
def msg_contains_greeting(nlp_entities, min_conf_threshold):
    return_val = False

    if (nlp_entities.get('greetings')):
        if(nlp_entities['greetings'][0]['confidence'] > min_conf_threshold):
            return_val = True

    return(return_val)

def get_strongest_intent(nlp_entities, min_confidence_threshold):
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

def send_message(user_id, msg_text):
    """
    Send the message msg_text to recipient.
    """
    headers = {
        'Content-type': 'application/json'
    }
    params = {
        "access_token": get_page_access_token()
    }
    data = json.dumps({
        "recipient": {"id": user_id},
        "message": {"text": msg_text.decode('unicode_escape')}
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

def is_first_time_user(user_id):
    print("DEBUG: Checking if user %s exists" % user_id)
    current_user = User.query.filter_by(fb_id=user_id).one_or_none()
    print("DEBUG: User %r" % current_user)
    return True if (current_user is None) else False

def send_welcome_message(user_id):
    firstname = get_users_firstname(user_id)
    msg = "Hello "+firstname+", I'm StudyBot. Nice to meet you!"
    send_message(user_id, msg)
    #TODO Add instructions for the user.

def send_greeting_message(user_id):
    from random import randint
    phrase = RANDOM_PHRASES[randint(0, len(RANDOM_PHRASES)-1)]
    msg = phrase % get_users_firstname(user_id)
    send_message(user_id, msg)

def create_user(user_id):
    new_user = User(fb_id=user_id)
    db.session.add(new_user)
    db.session.commit()

def create_new_fact(user_id, new_fact):
    user = User.query.filter_by(fb_id=user_id)
    new_fact_record = Fact(user_id=user.id, fact=new_fact)
    db.session.add(new_fact_record)
    db.session.commit()

def get_user_facts(user_id):
    return jsonify(user=[i.serialize for i in User.query.filter_by(fb_id=user_id)])

def delete_fact(user_id, fact):
    user = User.query.filter_by(fb_id=user_id)
    fact_record = Fact(user_id=user.id, fact=fact)
    db.session.delete(fact_record)
    db.session.commit()
#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    """
    Start the Flask app, the app will start listening for requests on port 5000.
    """
    app.run()
