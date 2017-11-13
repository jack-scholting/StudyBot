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
    print "Handling Verification."
    if request.args.get('hub.verify_token', '') == VERIF_TOKEN:
        print "Verification successful!"
        return request.args.get('hub.challenge', '')
    else:
        print "Verification failed!"
        return 'Error, wrong validation token'

"""
POST requests are for communication.
Handle POST requests by interpretting the user message, then sending the
appropriate response.
"""
@app.route('/', methods=['POST'])
def handle_messages():
    print "Handling Messages"
    payload = request.get_json()
    print payload

    if (payload):
        if (payload.get("object") == "page"):
            for entry in payload["entry"]:
                for messaging_event in entry["messaging"]:
                    if (messaging_event.get("message")):
                        sender_id = messaging_event["sender"]["id"]
                        message = messaging_event["message"]["text"]
                        print ("Incoming from %s: %s" % (sender_id, message))

                        if (is_first_time_user(sender_id)):
                            send_welcome_message(sender_id)

                        firstname = get_users_firstname(sender_id)
                        msg_text = "Hello " +firstname+" : " + message.decode('unicode_escape')
                        send_message(sender_id, msg_text)
        else:
            print("Error: Object is not a page.")
    else:
        print("Error: POST payload was empty.")

    return ("ok", 200)

#{"object":"page","entry":[{"id":"601541080185276","time":1510540428610,"messaging":[{"sender":{"id":"1778507745603521"},"recipient":{"id":"601541080185276"},"timestamp":1510540427576,"message":{"mid":"mid.$cAAIjGS-LkRZl5H8JOFfsznCC7186","seq":8657,"text":"Hello there handsome!","nlp":{"entities":{"greetings":[{"confidence":0.99972563983248,"value":"true"}]}}}}]}]}

#===============================================================================
# Helper Routines
#===============================================================================
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
        print r.text

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
