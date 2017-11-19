from flask import Flask, request
import json
import requests
import os

# Create the Flask application instance.
app = Flask(__name__)

#===============================================================================
# Global Data
#===============================================================================

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
                        #TODO
                        pass

                    if (messaging_event.get("message")):
                        """
                        Note: The ID is a page-scoped ID (PSID). It is a unique
                        identifier for a given person interacting with a given page.
                        """
                        sender_id = messaging_event["sender"]["id"]
                        message = messaging_event["message"]["text"]
                        nlp = messaging_event["message"]["nlp"]
                        print("DEBUG: Incoming from %s: %s" % (sender_id, message))

                        change_typing_indicator(enabled=True, user_id=sender_id)

                        #TODO - refactor to follow guidance from https://developers.facebook.com/docs/messenger-platform/discovery/welcome-screen
                        if (is_first_time_user(sender_id)):
                            send_welcome_message(sender_id)

                        for nlp_entity in nlp["entities"]:
                            #TODO
                            pass

                        #TODO we will need to add some handling for modes, for conversation flows.

                        firstname = get_users_firstname(sender_id)
                        msg_text = "Hello " +firstname+" : " + message.decode('unicode_escape')
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

    url = "https://graph.facebook.com/v2.6/me/messages"

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

    # Send a POST to Facebook's Graph API.
    r = requests.post(url=url, params=params, data=data, headers=headers)

    # Check the returned status code of the POST.
    if r.status_code != requests.codes.ok:
        print("DEBUG: " + r.text)

def send_message(user_id, msg_text):
    """
    Send the message msg_text to recipient.
    """
    url = "https://graph.facebook.com/v2.6/me/messages"

    headers = {
        'Content-type': 'application/json'
    }
    params = {
        "access_token": get_page_access_token()
    }
    data = json.dumps({
        "recipient": {"id": user_id},
        "message": {"text": msg_text}
    })

    # Send a POST to Facebook's Graph API.
    r = requests.post(url=url, params=params, data=data, headers=headers)

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
