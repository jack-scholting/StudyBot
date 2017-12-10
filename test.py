import os
import studybot
import unittest
import tempfile
import json
from unittest.mock import patch, Mock
from fakeredis import FakeRedis

RESPONSES = []
DUMMY_SENDER_ID = "0000000000"
DUMMY_SENDER_RECIPIENT_ID = "0000000000"
DUMMY_FIRST_NAME = "Unit Test"
DUMMY_PAYLOAD = {
    "object": "page",
    "entry": [{
        "time": 1511626204819,
        "id": "601541080185276",
        "messaging": [{
            "message": {
                "text": "",
                "seq": 3375,
                "mid": "mid.$cAAJ56m74wlhmJQ9M6Vf88n9j4aGT",
                "nlp": {}
            },
            "timestamp": 1511623623913,
            "sender": {
                "id": DUMMY_SENDER_ID
            },
            "recipient": {
                "id": DUMMY_SENDER_RECIPIENT_ID
            }
        }]
    }]
}


def get_intent_object(intent):
    return {
        "confidence": 0.99923574923073,
        "value": intent
    }


def get_greetings_object():
    return {
        "greetings": [{
            "confidence": 0.99923574923073
        }]
    }


def get_payload(text, entities):
    payload = DUMMY_PAYLOAD
    messaging_event = payload["entry"][0]["messaging"][0]
    messaging_event["message"]["text"] = text
    messaging_event["message"]["nlp"]["entities"] = {}
    messaging_event["message"]["nlp"]["entities"]["intent"] = []
    for entity in entities:
        if entity.get("greetings"):
            messaging_event["message"]["nlp"]["entities"] = entity
        else:
            messaging_event["message"]["nlp"]["entities"]["intent"].append(entity)
    payload["entry"][0]["messaging"][0] = messaging_event
    return payload


def get_welcome_message():
    return "Hello " + DUMMY_FIRST_NAME + ", I'm StudyBot. Nice to meet you!"


def get_greeting_messages():
    random_phrases = []
    for phrase in studybot.RANDOM_PHRASES:
        random_phrases.append(phrase % DUMMY_FIRST_NAME)
    return random_phrases


def get_fact_created_message():
    msg = "Ok, I created the following question and answer:\n"
    msg += "Question: %s\n" % studybot.current_user.tmp_fact.question
    msg += "Answer: %s" % studybot.current_user.tmp_fact.answer
    return msg


def mocked_send_request(*args, **kwargs):
    user_id = args[0]
    msg_text = args[1]
    is_response = True
    if len(args) > 2:
        is_response = args[2]

    """
    Send the message msg_text to recipient.
    """

    if (is_response):
        msg_type = "RESPONSE"
    else:
        msg_type = "NON_PROMOTIONAL_SUBSCRIPTION"

    data = {
        "message_type": msg_type,
        "recipient": {"id": user_id},
        "message": {"text": msg_text}
    }

    RESPONSES.append(data)


def remove_test_data():
    test_user = studybot.User.query.filter_by(fb_id=DUMMY_SENDER_ID).one_or_none()
    if test_user:
        if test_user.facts:
            for fact in test_user.facts:
                studybot.db.session.delete(fact)
        studybot.db.session.delete(test_user)
        studybot.db.session.commit()
    global RESPONSES
    RESPONSES = []


class StudyBotTestCase(unittest.TestCase):
    def setUp(self):
        studybot.app.testing = True
        self.app = studybot.app.test_client()
        with studybot.app.app_context():
            studybot.change_typing_indicator = Mock()
            studybot.get_users_firstname = Mock(return_value=DUMMY_FIRST_NAME)
            studybot.send_message = Mock(side_effect=mocked_send_request)
            studybot.db.create_all()

    def tearDown(self):
        remove_test_data()

    @patch('studybot.cache', FakeRedis())
    def test_create_user(self):
        payload = get_payload("Hey StudyBot!", [get_greetings_object()])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(RESPONSES[0]["message"]["text"], get_welcome_message())

    @patch('studybot.cache', FakeRedis())
    def test_greetings(self):
        studybot.create_user(DUMMY_SENDER_ID)
        payload = get_payload("Hey StudyBot!", [get_greetings_object()])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(RESPONSES, [])
        self.assertIn(RESPONSES[0]["message"]["text"], get_greeting_messages())

    @patch('studybot.cache', FakeRedis())
    def test_create_fact(self):
        studybot.create_user(DUMMY_SENDER_ID)
        payload = get_payload("I want to create a fact", [get_intent_object("add_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is a question?", [get_intent_object("add_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is answer.", [get_intent_object("add_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's add that new fact. What is the question?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Thanks, what's the answer to that question?")
        self.assertEqual(RESPONSES[2]["message"]["text"], get_fact_created_message())


if __name__ == '__main__':
    unittest.main()
