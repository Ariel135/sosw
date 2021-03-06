import boto3
import json
import logging
import shutil
import unittest
import uuid
import os
import csv

from collections import defaultdict
from unittest.mock import MagicMock
from sosw.components.sns import *


logging.getLogger('botocore').setLevel(logging.WARNING)

os.environ["STAGE"] = "test"
os.environ["autotest"] = "True"


class sns_TestCase(unittest.TestCase):

    def clean_queue(self):
        setattr(self.sns, 'queue', [])


    def setUp(self):
        self.sns = SnsManager(test=True, subject='Autotest SNS Subject')
        self.sns.commit = MagicMock(side_effect=self.clean_queue)

    def tearDown(self):
        pass


    def test_init__reads_config(self):

        sns = SnsManager(config={'subject': 'subj', 'recepient': 'arn::some_topic'})

        self.assertEqual(sns.recipient, 'arn:aws:sns:us-west-2:000000000000:autotest_topic',
                         "The Topic must be automatically reset for test")
        self.assertEqual(sns.subject, 'subj', "Subject was not set during __init__ from config.")


    def test_queue_message(self):
        self.sns.send_message("test message")
        self.assertEqual(len(self.sns.queue), 1, "Default send_message() did not queue the message.")


    def test_queue_message_with_subject(self):
        self.sns.send_message("test message", subject="New Subject")
        self.assertEqual(len(self.sns.queue), 1, "send_message() with custom subject did not queue.")


    def test_commit_queue(self):
        self.sns.send_message("test message")
        self.sns.commit()
        self.assertEqual(len(self.sns.queue), 0, f"Commit did not clean queue")
        self.sns.commit.assert_called_once()


    def test_commit_on_change_subject(self):
        self.sns.send_message("test message")
        self.sns.set_subject("New Subject")
        self.assertEqual(len(self.sns.queue), 0, "On change subject the queue should be committed.")


    def test_no_commit_on_change_subject_if_subject_is_same(self):
        self.sns.send_message("test message")
        self.sns.set_subject("Autotest SNS Subject")
        self.assertEqual(len(self.sns.queue), 1, "On change subject the queue should be committed.")


    def test_no_commit_on_same_subject(self):
        self.sns.send_message("test message")
        self.sns.send_message("test message", subject="Autotest SNS Subject")
        self.assertEqual(len(self.sns.queue), 2, "On sending message with exactly same subject, it should be queued.")


    def test_commit_and_queue_on_change_subject(self):
        self.sns.send_message("test message")
        self.assertEqual(len(self.sns.queue), 1)
        self.sns.send_message("test message", subject="New Subject")
        self.assertEqual(len(self.sns.queue), 1, "On change subject, old message should be committed, new one queued.")


    def test_commit_auto_on_change_recipient(self):
        self.sns.send_message("test message")
        self.assertEqual(len(self.sns.queue), 1, f"Initial send_message() did not queue the message")

        self.sns.set_recipient('arn:aws:sns:new_recipient')
        self.assertEqual(len(self.sns.queue), 0)


    def test_no_commit_on_change_recipient_if_recipient_is_same(self):
        self.sns.send_message("test message")
        self.assertEqual(len(self.sns.queue), 1, f"Initial send_message() did not queue the message")

        self.sns.set_recipient('arn:aws:sns:us-west-2:000000000000:autotest_topic')
        self.assertEqual(len(self.sns.queue), 1)


    def test_validate_recipient(self):
        """
        Must be a string with ARN of SNS Topic. Validator just checks that string starts with 'arn:aws:'
        """
        self.assertRaises(AssertionError, self.sns.set_recipient, 'just_new_recipient_not_full_arn')


    def test_create_topic_invalid_name(self):
        with self.assertRaises(RuntimeError) as exc:
            self.sns.create_topic('')

        self.assertEqual(str(exc.exception), "You passed invalid topic name")

    def test_create_topic_return_value(self):
        self.sns.client = MagicMock()
        self.sns.client.create_topic = MagicMock(return_value={'TopicArn': 'test_arn'})
        self.assertEqual(self.sns.create_topic('topic_name'), 'test_arn')


    def test_create_subscription_invalid_params(self):
        with self.assertRaises(RuntimeError) as exc:
            self.sns.create_subscription('', 'protocol', 'endpoint')

        self.assertEqual(str(exc.exception), "You must send valid topic ARN, Protocol and Endpoint to add a subscription")


    def test_get_message_attribute_validate_output(self):
        self.assertEqual(self.sns.get_message_attribute(10), {'DataType': 'Number', 'StringValue': '10'})
        self.assertEqual(self.sns.get_message_attribute(10.99), {'DataType': 'Number', 'StringValue': '10.99'})
        self.assertEqual(self.sns.get_message_attribute('Test'), {'DataType': 'String', 'StringValue': 'Test'})
        self.assertEqual(
            self.sns.get_message_attribute(['Test1', 'Test2', 'Test3']),
            {'DataType': 'String.Array', 'StringValue': json.dumps(['Test1', 'Test2', 'Test3'])}
        )


    def test_commit_on_change_message_attributes(self):
        self.sns.send_message("test message")
        self.assertEqual(len(self.sns.queue), 1, "There is 1 message in the queue.")
        self.sns.send_message("test message", message_attributes={'price': 100})
        self.assertEqual(len(self.sns.queue), 1, "On change message_attributes, old message should be committed, "
                                                 "new one queued.")
        self.sns.send_message("test message", message_attributes={'price': 100})
        self.assertEqual(len(self.sns.queue), 2, "On sending message with exactly same message_attributes, it should "
                                                 "be queued.")
        self.sns.send_message("test message", message_attributes={'price': 100, 'cancellation': True})
        self.assertEqual(len(self.sns.queue), 1, "On sending message with different message_attributes, old messages "
                                                 "should be committed. New one should be queued.")


if __name__ == '__main__':
    unittest.main()
