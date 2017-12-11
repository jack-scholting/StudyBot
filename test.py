import studybot
import unittest
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


def get_intent_object(intent, confidence=0.99923574923073):
    return {
        "confidence": confidence,
        "value": intent
    }


def get_greetings_object():
    return {
        "greetings": [{
            "confidence": 0.99923574923073
        }]
    }


def get_duration_object(seconds):
    return {
        "confidence": 0.99923574923073,
        "normalized": {
            "value": seconds
        }
    }


def get_payload(text, entities):
    payload = DUMMY_PAYLOAD
    messaging_event = payload["entry"][0]["messaging"][0]
    messaging_event["message"]["text"] = text
    messaging_event["message"]["nlp"]["entities"] = {}
    for entity in entities:
        if entity.get("greetings"):
            messaging_event["message"]["nlp"]["entities"] = entity
        elif entity.get("normalized"):
            if not messaging_event["message"]["nlp"]["entities"].get("duration"):
                messaging_event["message"]["nlp"]["entities"]["duration"] = []
            messaging_event["message"]["nlp"]["entities"]["duration"].append(entity)
        else:
            if not messaging_event["message"]["nlp"]["entities"].get("intent"):
                messaging_event["message"]["nlp"]["entities"]["intent"] = []
            messaging_event["message"]["nlp"]["entities"]["intent"].append(entity)
    payload["entry"][0]["messaging"][0] = messaging_event
    return payload


def get_welcome_message():
    return "Hello " + DUMMY_FIRST_NAME + ", I'm StudyBot. Nice to meet you! " + studybot.USAGE_INSTRUCTIONS


def get_greeting_messages():
    random_phrases = []
    for phrase in studybot.RANDOM_PHRASES:
        random_phrases.append(phrase % DUMMY_FIRST_NAME)
    return random_phrases


def get_fact_created_updated_message(created=True):
    added_updated = "created" if created else "updated"
    msg = "Ok, I %s the following question and answer:\n" % added_updated
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
    FakeRedis().flushall()


def create_dummy_fact(question, answer):
    user_data = studybot.get_user(DUMMY_SENDER_ID)
    fact = studybot.Fact(user_id=user_data.id)
    fact.question = question
    fact.answer = answer
    return fact


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
        self.assertEqual(RESPONSES[2]["message"]["text"], get_fact_created_updated_message())

        new_fact = studybot.get_fact(studybot.current_user.tmp_fact.question)
        self.assertIsNotNone(new_fact)

    @patch('studybot.cache', FakeRedis())
    def test_create_fact_long_question(self):
        studybot.create_user(DUMMY_SENDER_ID)
        payload = get_payload("I want to create a fact", [get_intent_object("add_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        import string
        import random

        long_string = ''.join(random.choice(string.ascii_lowercase) for i in range(studybot.FB_MAX_MESSAGE_LENGTH + 10))
        payload = get_payload(long_string, [get_intent_object("add_fact")])
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
        self.assertEqual(len(RESPONSES), 4)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's add that new fact. What is the question?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Thanks, what's the answer to that question?")
        self.assertEqual(RESPONSES[2]["message"]["text"] + RESPONSES[3]["message"]["text"], get_fact_created_updated_message())

        new_fact = studybot.get_fact(studybot.current_user.tmp_fact.question)
        self.assertIsNotNone(new_fact)

    @patch('studybot.cache', FakeRedis())
    def test_update_fact(self):
        studybot.create_user(DUMMY_SENDER_ID)
        dummy_fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(dummy_fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = dummy_fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to change a fact", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Fact with id " + str(fact_id), [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is a question?", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is answer.", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 4)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want to change?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Ok, let's update that fact. What is the question?")
        self.assertEqual(RESPONSES[2]["message"]["text"], "Thanks, what's the answer to that question?")
        self.assertEqual(RESPONSES[3]["message"]["text"], get_fact_created_updated_message(False))

        fact = studybot.get_fact(studybot.current_user.tmp_fact.question)
        self.assertIsNotNone(fact)
        self.assertNotEqual(dummy_fact.question, fact.question)
        self.assertNotEqual(dummy_fact.answer, fact.answer)

    @patch('studybot.cache', FakeRedis())
    def test_update_fact_with_id(self):
        studybot.create_user(DUMMY_SENDER_ID)
        dummy_fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(dummy_fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = dummy_fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to change fact " + str(fact_id), [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is a question?", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("This is answer.", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's update that fact. What is the question?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Thanks, what's the answer to that question?")
        self.assertEqual(RESPONSES[2]["message"]["text"], get_fact_created_updated_message(False))

        fact = studybot.get_fact(studybot.current_user.tmp_fact.question)
        self.assertIsNotNone(fact)
        self.assertNotEqual(dummy_fact.question, fact.question)
        self.assertNotEqual(dummy_fact.answer, fact.answer)


    @patch('studybot.cache', FakeRedis())
    def test_update_fact_not_found(self):
        studybot.create_user(DUMMY_SENDER_ID)

        fact_id = -1

        payload = get_payload("I want to change a fact", [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Fact with id " + str(fact_id), [get_intent_object("change_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want to change?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Whoops! We don't have a fact for you. Try viewing your facts to get the ID.")


    @patch('studybot.cache', FakeRedis())
    def test_delete_fact(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to delete a fact", [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Fact with id " + str(fact_id), [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Yes", [get_intent_object("confirmation")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        bot_msg = "Are you sure you want to delete this fact?\n"
        bot_msg += "Question: %s\n" % fact.question

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want to delete?")
        self.assertEqual(RESPONSES[1]["message"]["text"], bot_msg)
        self.assertEqual(RESPONSES[2]["message"]["text"], "Fact deleted successfully.")

        fact = studybot.get_fact(fact_id)
        self.assertIsNone(fact)

    @patch('studybot.cache', FakeRedis())
    def test_delete_fact_with_id(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to delete fact " + str(fact_id), [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Yes", [get_intent_object("confirmation")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)
        bot_msg = "Are you sure you want to delete this fact?\n"
        bot_msg += "Question: %s\n" % fact.question

        self.assertEqual(RESPONSES[0]["message"]["text"], bot_msg)
        self.assertEqual(RESPONSES[1]["message"]["text"], "Fact deleted successfully.")

        fact = studybot.get_fact(fact_id)
        self.assertIsNone(fact)

    @patch('studybot.cache', FakeRedis())
    def test_delete_fact_cancel(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to delete fact " + str(fact_id), [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("No", [get_intent_object("negation")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)
        bot_msg = "Are you sure you want to delete this fact?\n"
        bot_msg += "Question: %s\n" % fact.question

        self.assertEqual(RESPONSES[0]["message"]["text"], bot_msg)
        self.assertEqual(RESPONSES[1]["message"]["text"], "Ok, I won't delete this fact.")

        fact = studybot.get_fact(fact_id)
        self.assertIsNotNone(fact)

    @patch('studybot.cache', FakeRedis())
    def test_delete_fact_not_found(self):
        studybot.create_user(DUMMY_SENDER_ID)

        fact_id = -1

        payload = get_payload("I want to delete a fact", [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Fact with id " + str(fact_id), [get_intent_object("delete_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)
        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want to delete?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Whoops! We don't have a fact for you. Try viewing your facts to get the ID.")

    @patch('studybot.cache', FakeRedis())
    def test_strongest_intent(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact = create_dummy_fact("Dummy Question", "Dummy Answer")
        studybot.set_user(studybot.ConvoState(fact.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact
        studybot.create_fact()

        fact_id = studybot.current_user.tmp_fact.id

        payload = get_payload("I want to delete fact " + str(fact_id), [get_intent_object("delete_fact"), get_intent_object("change_fact", 0.8503043)])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)
        bot_msg = "Are you sure you want to delete this fact?\n"
        bot_msg += "Question: %s\n" % fact.question

        self.assertEqual(RESPONSES[0]["message"]["text"], bot_msg)

    @patch('studybot.cache', FakeRedis())
    def test_view_facts(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact_id1 = studybot.current_user.tmp_fact.id

        fact2 = create_dummy_fact("Dummy Question 2", "Dummy Answer 2")
        studybot.set_user(studybot.ConvoState(fact2.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact2
        studybot.create_fact()
        fact_id2= studybot.current_user.tmp_fact.id

        payload = get_payload("View facts", [get_intent_object("view_facts")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        bot_msg1 = "%d. %s\n" % (fact_id1, fact1.question)
        bot_msg2 = "%d. %s\n" % (fact_id2, fact2.question)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, here are the facts we have.")
        self.assertEqual(RESPONSES[1]["message"]["text"], bot_msg1)
        self.assertEqual(RESPONSES[2]["message"]["text"], bot_msg2)

    @patch('studybot.cache', FakeRedis())
    def test_view_facts_no_facts(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("View facts", [get_intent_object("view_facts")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Whoops! We don't have any facts for you try adding a new fact.")

    @patch('studybot.cache', FakeRedis())
    def test_view_fact_detail(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact_id1 = studybot.current_user.tmp_fact.id

        payload = get_payload("View fact details", [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Fact Id " + str(fact_id1), [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        fact = studybot.get_fact(fact_id1)

        return_msg = "%d. %s\n" % (fact.id, fact.question)
        return_msg += "Answer: %s\n" % fact.answer
        return_msg += "Easiness: %s\n" % fact.easiness
        return_msg += "Consecutive Correct Answers: %s\n" % fact.consecutive_correct_answers
        return_msg += "Next Study Time: %s\n" % studybot.format_date_time(fact.next_due_date)
        return_msg += "Last Seen: %s\n\n" % studybot.format_date_time(fact.last_seen)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want details for?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Here's the fact.")
        self.assertEqual(RESPONSES[2]["message"]["text"], return_msg)

    @patch('studybot.cache', FakeRedis())
    def test_view_fact_detail_with_id(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact_id1 = studybot.current_user.tmp_fact.id

        payload = get_payload("View fact with id " + str(fact_id1), [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)

        fact = studybot.get_fact(fact_id1)

        return_msg = "%d. %s\n" % (fact.id, fact.question)
        return_msg += "Answer: %s\n" % fact.answer
        return_msg += "Easiness: %s\n" % fact.easiness
        return_msg += "Consecutive Correct Answers: %s\n" % fact.consecutive_correct_answers
        return_msg += "Next Study Time: %s\n" % studybot.format_date_time(fact.next_due_date)
        return_msg += "Last Seen: %s\n\n" % studybot.format_date_time(fact.last_seen)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Here's the fact.")
        self.assertEqual(RESPONSES[1]["message"]["text"], return_msg)

    @patch('studybot.cache', FakeRedis())
    def test_view_fact_detail_with_id_not_found(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("View fact with id " + str(1), [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Whoops! We don't have a fact for you. Try viewing your facts to get the ID.")


    @patch('studybot.cache', FakeRedis())
    def test_view_fact_detail_not_found(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("View facts", [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("1", [get_intent_object("view_detailed_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, which fact do you want details for?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Whoops! We don't have a fact for you. Try viewing your facts to get the ID.")

    @patch('studybot.cache', FakeRedis())
    def test_silence_studying(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("Silence study", [get_intent_object("silence_studying")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("10 days", [get_duration_object(10 * 24 * 3600)])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)

        user = studybot.get_user(DUMMY_SENDER_ID)
        bot_msg = "Ok, silencing study notifications until " + str(user.silence_end_time) + "."

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, how long do you want to silence notifications for?")
        self.assertEqual(RESPONSES[1]["message"]["text"], bot_msg)

    @patch('studybot.cache', FakeRedis())
    def test_silence_studying_with_time(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("Silence study for 10 days", [get_duration_object(10 * 24 * 3600), get_intent_object("silence_studying")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)

        user = studybot.get_user(DUMMY_SENDER_ID)
        bot_msg = "Ok, silencing study notifications until " + str(user.silence_end_time) + "."

        self.assertEqual(RESPONSES[0]["message"]["text"], bot_msg)


    @patch('studybot.cache', FakeRedis())
    def test_silence_studying_invalid_time(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("Silence study", [get_intent_object("silence_studying")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("10 days", [get_intent_object("silence_studying")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 2)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, how long do you want to silence notifications for?")
        self.assertEqual(RESPONSES[1]["message"]["text"], "Sorry, I couldn't get a duration from that.")

    @patch('studybot.cache', FakeRedis())
    def test_study_fact(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact1.next_due_date = studybot.datetime.utcnow()
        studybot.db.session.commit()

        payload = get_payload("Study time!", [get_intent_object("study_next_fact")])
        print(payload)
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Dummy Answer 1", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("5", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's study!\n%s" % fact1.question)
        self.assertEqual(RESPONSES[1]["message"]["text"], "Here is the answer:\n%s\nHow hard was that on a scale from 0 (impossible) to 5 (trivial)?" % fact1.answer)
        self.assertEqual(RESPONSES[2]["message"]["text"], "Got it, fact studied!")

        fact = studybot.get_fact(fact1.id)
        self.assertEqual(fact.consecutive_correct_answers, 1)
        self.assertGreaterEqual(fact.easiness, fact1.easiness)
        self.assertGreater(fact.next_due_date, fact1.next_due_date)

    @patch('studybot.cache', FakeRedis())
    def test_study_fact_low_perf(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact1.next_due_date = studybot.datetime.utcnow()
        studybot.db.session.commit()

        payload = get_payload("Study time!", [get_intent_object("study_next_fact")])
        print(payload)
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Dummy Answer 1", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("2", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's study!\n%s" % fact1.question)
        self.assertEqual(RESPONSES[1]["message"]["text"],
                         "Here is the answer:\n%s\nHow hard was that on a scale from 0 (impossible) to 5 (trivial)?" % fact1.answer)
        self.assertEqual(RESPONSES[2]["message"]["text"], "Got it, fact studied!")

        fact = studybot.get_fact(fact1.id)
        self.assertEqual(fact.consecutive_correct_answers, 0)
        self.assertLessEqual(fact.easiness, fact1.easiness)
        self.assertGreaterEqual(fact.next_due_date, fact1.next_due_date)

    @patch('studybot.cache', FakeRedis())
    def test_study_fact_invalid_perf_value(self):
        studybot.create_user(DUMMY_SENDER_ID)
        fact1 = create_dummy_fact("Dummy Question 1", "Dummy Answer 1")
        studybot.set_user(studybot.ConvoState(fact1.user_id, studybot.State.DEFAULT))
        studybot.current_user.tmp_fact = fact1
        studybot.create_fact()
        fact1.next_due_date = studybot.datetime.utcnow()
        studybot.db.session.commit()

        payload = get_payload("Study time!", [get_intent_object("study_next_fact")])
        print(payload)
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("Dummy Answer 1", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        payload = get_payload("11", [get_intent_object("study_next_fact")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 3)

        self.assertEqual(RESPONSES[0]["message"]["text"], "Ok, let's study!\n%s" % fact1.question)
        self.assertEqual(RESPONSES[1]["message"]["text"], "Here is the answer:\n%s\nHow hard was that on a scale from 0 (impossible) to 5 (trivial)?" % fact1.answer)
        self.assertEqual(RESPONSES[2]["message"]["text"], "I didn't get a number from that, can you try again on a scale from 0 to 5?")

    @patch('studybot.cache', FakeRedis())
    def test_study_fact_no_facts_to_study(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("Study time!", [get_intent_object("study_next_fact")])
        print(payload)
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)

        self.assertEqual(RESPONSES[0]["message"]["text"], "No studying needed! You're all caught up.")

    @patch('studybot.cache', FakeRedis())
    def test_invalid_intent(self):
        studybot.create_user(DUMMY_SENDER_ID)

        payload = get_payload("Dummy intent!", [get_intent_object("default_intent")])
        headers = {
            'Content-type': 'application/json'
        }
        response = self.app.post('/', data=json.dumps(payload), headers=headers)
        self.assertEqual(response.status_code, 200)

        self.assertNotEqual(RESPONSES, [])
        self.assertEqual(len(RESPONSES), 1)

        self.assertEqual(RESPONSES[0]["message"]["text"], "I'm not sure what you mean." + " " + studybot.USAGE_INSTRUCTIONS)


if __name__ == '__main__':
    unittest.main()
