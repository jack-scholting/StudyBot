from flask import Flask, request
import json
import requests

# Create the Flask application instance.
app = Flask(__name__)

#===============================================================================
# Global Data
#===============================================================================
"""
This PAT (Page Access Token) is used to authenticate our requests/responses.
It was generated during the setup of our Facebook page and Facebook app.
"""
#TODO - this is not secure, since it is hardcoded and published to Github. We need to convert this into an environment variable.
PAT = 'EAABxbRfQPaUBACGzDsUxXidpFSfZAz96jBTY8mcz1fCTbSL7fNkyNxDRJjB2tKpTZCKrwglBCpqz4j4OMpObkbMsqxIsvxNwAxtyXZCF8Q4X1nNUsknAYkwP79domsnsO3a9g0ZBZCuz4GzWy6HtZCq0phQ7nyIF5Dwl1vuLr6ngZDZD'

"""
This is a secret token we provide Facebook so we can verify the request is
actually coming from Facebook.
"""
VERIF_TOKEN = 'test_token'

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
    if request.args.get('hub.verify_token', '') == VERIF_TOKEN:
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
            for entry in payload["entry"]:
                for messaging_event in entry["messaging"]:
                    if (messaging_event.get("message")):
                        """
                        Note: The ID is a page-scoped ID (PSID). It is a unique
                        identifier for a given person interacting with a given page.
                        """
                        sender_id = messaging_event["sender"]["id"]
                        message = messaging_event["message"]["text"]
                        nlp = messaging_event["message"]["nlp"]
                        print("DEBUG: Incoming from %s: %s" % (sender_id, message))

                        change_typing_indicator(enabled=True, sender_id)

                        #TODO - refactor to follow guidance from https://developers.facebook.com/docs/messenger-platform/discovery/welcome-screen
                        if (is_first_time_user(sender_id)):
                            send_welcome_message(sender_id)

                        firstname = get_users_firstname(sender_id)
                        msg_text = "Hello " +firstname+" : " + message.decode('unicode_escape')
                        send_message(sender_id, msg_text)

                        change_typing_indicator(enabled=False, sender_id)
        else:
            print("DEBUG: Error: Object is not a page.")
    else:
        print("DEBUG: Error: POST payload was empty.")

    """
    Per the documentation, the webhook should always return "200 OK", otherwise
    the webhook may be unsubscribed from the Messenger Platform.
    """
    return ("ok", 200)

#{"object":"page","entry":[{"id":"601541080185276","time":1510540428610,"messaging":[{"sender":{"id":"1778507745603521"},"recipient":{"id":"601541080185276"},"timestamp":1510540427576,"message":{"mid":"mid.$cAAIjGS-LkRZl5H8JOFfsznCC7186","seq":8657,"text":"Hello there handsome!","nlp":{"entities":{"greetings":[{"confidence":0.99972563983248,"value":"true"}]}}}}]}]}

#===============================================================================
# Helper Routines
#===============================================================================
def change_typing_indicator(enabled=True, user_id):
    if(enabled):
        action = "typing_on"
    else:
        action = "typing_off"

    # Send a POST to Facebook's Graph API.
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
        params={"access_token": PAT},
        data=json.dumps({
        "recipient": {"id": user_id},
        "sender_action": action
        }),
        headers={'Content-type': 'application/json'})

    # Check the returned status code of the POST.
    if r.status_code != requests.codes.ok:
        print("DEBUG: " + r.text)

def send_message(user_id, msg_text):
    """
    Send the message msg_text to recipient.
    """
    # Send a POST to Facebook's Graph API.
    r = requests.post("https://graph.facebook.com/v2.6/me/messages",
        params={"access_token": PAT},
        data=json.dumps({
        "recipient": {"id": user_id},
        "message": {"text": msg_text}
        }),
        headers={'Content-type': 'application/json'})

    # Check the returned status code of the POST.
    if r.status_code != requests.codes.ok:
        print("DEBUG: " + r.text)

"""
Explaination at https://developers.facebook.com/docs/messenger-platform/identity/user-profile
"""
def get_users_firstname(user_id):
    r = requests.get("https://graph.facebook.com/v2.6/"+str(user_id),
            params={"access_token" : PAT,
                    "fields" : "first_name"})
    json_response = json.loads(r.text)
    return (json_response["first_name"])

def is_first_time_user(user_id):
    #TODO Check database for user.
    return (False)

def send_welcome_message(user_id):
    firstname = get_users_firstname(user_id)
    msg = "Hello "+firstname+", I'm StudyBot. Nice to meet you!"
    send_message(user_id, msg)
    #TODO Add instructions for the user.


#===============================================================================
# Main
#===============================================================================
if __name__ == '__main__':
    """
    Start the Flask app, the app will start listening for requests on port 5000.
    """
    app.run()
