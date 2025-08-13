import unittest
from unittest.mock import patch, MagicMock
import json
import os
from datetime import datetime

from ..weather_processor.lambda_function import lambda_handler, handle_notification

class TestWeatherProcessorLambdaFunction(unittest.TestCase):

    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_handle_notification_sms(self, mock_boto_client):
        mock_sns_client = MagicMock()
        mock_boto_client.return_value = mock_sns_client
        weather_body = {
            'notification_type': 'sms',
            'data': {'weather': [{'description': 'Rainy'}]},
            'city_name': 'TestCity',
            'phone_number': '+1234567890'
        }
        sns_topic_arn = 'arn:aws:sns:region:account-id:weather-topic'

        handle_notification(weather_body, sns_topic_arn)

        mock_sns_client.publish.assert_called_once_with(
            TopicArn=sns_topic_arn,
            Message='Weather condition for TestCity - Rainy',
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': 'WEATHER'
                },
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )


    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_handle_notification_email(self, mock_boto_client):
        mock_sns_client = MagicMock()
        mock_boto_client.return_value = mock_sns_client
        weather_body = {
            'notification_type': 'email',
            'data': {'weather': [{'description': 'Sunny'}]},
            'city_name': 'TestCity',
            'email': 'test@example.com'
        }
        sns_topic_arn = 'arn:aws:sns:region:account-id:weather-topic'

        handle_notification(weather_body, sns_topic_arn)

        mock_sns_client.publish.assert_called_once_with(
            TopicArn=sns_topic_arn,
            Subject='Weather condition for TestCity',
            Message='Weather Condition for TestCity - Sunny',
            MessageStructure='text',
            MessageAttributes={
                'email': {
                    'DataType': 'String',
                    'StringValue': 'test@example.com'
                }
            }
        )


    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_handle_notification_sms_and_email(self, mock_boto_client):
        mock_sns_client = MagicMock()
        mock_boto_client.return_value = mock_sns_client
        weather_body = {
            'notification_type': 'both',
            'data': {'weather': [{'description': 'Cloudy'}]},
            'city_name': 'TestCity',
            'phone_number': '+1234567890',
            'email': 'test@example.com'
        }
        sns_topic_arn = 'arn:aws:sns:region:account-id:weather-topic'

        handle_notification(weather_body, sns_topic_arn)

        self.assertEqual(2, mock_sns_client.publish.call_count)
        mock_sns_client.publish.assert_any_call(
            TopicArn=sns_topic_arn,
            Message='Weather condition for TestCity - Cloudy',
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': 'WEATHER'
                },
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        mock_sns_client.publish.assert_any_call(
            TopicArn=sns_topic_arn,
            Subject='Weather condition for TestCity',
            Message='Weather Condition for TestCity - Cloudy',
            MessageStructure='text',
            MessageAttributes={
                'email': {
                    'DataType': 'String',
                    'StringValue': 'test@example.com'
                }
            }
        )

    # New test cases for lambda_handler

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    @patch('src.lambda.weather_processor.lambda_function.handle_notification')
    def test_lambda_handler_success(self, mock_handle_notification, mock_boto_client):
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        # Test event
        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'email',
                    'data': {'weather': [{'description': 'Sunny', 'temp': 25}]},
                    'city_name': 'TestCity',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        # Execute
        result = lambda_handler(test_event, context)

        # Assertions
        self.assertEqual(result['statusCode'], 200)
        self.assertEqual(result['body'], test_event)

        # Verify S3 put_object was called
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args
        self.assertEqual(call_args.kwargs['Bucket'], 'test-weather-bucket')
        self.assertTrue(call_args.kwargs['Key'].startswith('weather-data/'))
        self.assertTrue(call_args.kwargs['Key'].endswith('.json'))
        self.assertEqual(call_args.kwargs['ContentType'], 'application/json')

        # Verify handle_notification was called
        mock_handle_notification.assert_called_once()

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    @patch('src.lambda.weather_processor.lambda_function.handle_notification')
    def test_lambda_handler_with_sms_notification(self, mock_handle_notification, mock_boto_client):
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        # Test event with SMS notification
        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'sms',
                    'data': {'weather': [{'description': 'Rainy', 'temp': 18}]},
                    'city_name': 'NewYork',
                    'phone_number': '+1234567890'
                })
            }]
        }

        context = {}

        # Execute
        result = lambda_handler(test_event, context)

        # Assertions
        self.assertEqual(result['statusCode'], 200)
        mock_s3_client.put_object.assert_called_once()
        mock_handle_notification.assert_called_once()

        # Verify the weather data was formatted correctly
        call_args = mock_s3_client.put_object.call_args
        stored_data = json.loads(call_args.kwargs['Body'])
        self.assertEqual(stored_data['weather'][0]['description'], 'Rainy')
        self.assertEqual(stored_data['weather'][0]['temp'], 18)

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_lambda_handler_s3_error_with_notification(self, mock_boto_client):
        # Setup mocks - S3 fails, SNS succeeds
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_s3_client.put_object.side_effect = Exception("S3 connection failed")
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'email',
                    'data': {'weather': [{'description': 'Stormy'}]},
                    'city_name': 'TestCity',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        # Execute
        with self.assertRaises(Exception) as context:
            lambda_handler(test_event, None)

        self.assertTrue("S3 connection failed" in str(context.exception))

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_lambda_handler_invalid_json_in_event(self, mock_boto_client):
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        # Test event with invalid JSON
        test_event = {'invalid_key': 'invalid_value'}

        context = {}

        # Execute

        with self.assertRaises(KeyError):
            lambda_handler(test_event, None)

        mock_s3_client.put_object.assert_not_called()

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    @patch('src.lambda.weather_processor.lambda_function.handle_notification')
    def test_lambda_handler_both_notifications(self, mock_handle_notification, mock_boto_client):
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        # Test event with both SMS and email
        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'both',
                    'data': {'weather': [{'description': 'Partly Cloudy', 'temp': 22, 'humidity': 65}]},
                    'city_name': 'London',
                    'phone_number': '+1234567890',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        # Execute
        result = lambda_handler(test_event, context)

        # Assertions
        self.assertEqual(result['statusCode'], 200)
        mock_s3_client.put_object.assert_called_once()
        mock_handle_notification.assert_called_once()

        # Verify the complete weather data was stored
        call_args = mock_s3_client.put_object.call_args
        stored_data = json.loads(call_args.kwargs['Body'])
        self.assertEqual(stored_data['weather'][0]['description'], 'Partly Cloudy')
        self.assertEqual(stored_data['weather'][0]['temp'], 22)
        self.assertEqual(stored_data['weather'][0]['humidity'], 65)

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    def test_lambda_handler_error_notification_fails(self, mock_boto_client):
        # Setup mocks - both S3 and SNS fail
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_s3_client.put_object.side_effect = Exception("S3 Error")
        mock_sns_client.publish.side_effect = Exception("SNS Error")
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'email',
                    'data': {'weather': [{'description': 'Snow'}]},
                    'city_name': 'TestCity',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        with self.assertRaises(Exception) as context:
            lambda_handler(test_event, None)

        mock_s3_client.put_object.assert_called_once()
        mock_sns_client.publish.assert_called_once()
        self.assertTrue("S3 Error" in str(context.exception))

    def test_lambda_handler_missing_environment_variables(self):
        # Test without environment variables
        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'email',
                    'data': {'weather': [{'description': 'Sunny'}]},
                    'city_name': 'TestCity',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        # Execute - should fail due to missing env vars
        with self.assertRaises(KeyError):
            lambda_handler(test_event, context)

    @patch.dict(os.environ, {
        'S3_BUCKET_NAME': 'test-weather-bucket',
        'SNS_TOPIC_ARN': 'arn:aws:sns:region:account-id:weather-topic'
    })
    @patch('src.lambda.weather_processor.lambda_function.boto3.client')
    @patch('src.lambda.weather_processor.lambda_function.handle_notification')
    def test_lambda_handler_complex_weather_data(self, mock_handle_notification, mock_boto_client):
        # Setup mocks
        mock_s3_client = MagicMock()
        mock_sns_client = MagicMock()
        mock_boto_client.side_effect = lambda service: {
            's3': mock_s3_client,
            'sns': mock_sns_client
        }[service]

        # Test event with complex weather data
        complex_weather_data = {
            'weather': [{
                'description': 'Heavy Rain',
                'temp': 15,
                'humidity': 85,
                'pressure': 1013.25,
                'wind_speed': 12.5,
                'visibility': 5000
            }],
            'forecast': [
                {'day': 'tomorrow', 'description': 'Cloudy', 'temp': 18},
                {'day': 'day_after', 'description': 'Sunny', 'temp': 22}
            ]
        }

        test_event = {
            'Records': [{
                'body': json.dumps({
                    'notification_type': 'email',
                    'data': complex_weather_data,
                    'city_name': 'Paris',
                    'email': 'test@example.com'
                })
            }]
        }

        context = {}

        # Execute
        result = lambda_handler(test_event, context)

        # Assertions
        self.assertEqual(result['statusCode'], 200)
        mock_s3_client.put_object.assert_called_once()

        # Verify the complex data was stored correctly
        call_args = mock_s3_client.put_object.call_args
        stored_data = json.loads(call_args.kwargs['Body'])
        self.assertEqual(stored_data['weather'][0]['description'], 'Heavy Rain')
        self.assertEqual(len(stored_data['forecast']), 2)
        self.assertEqual(stored_data['forecast'][0]['day'], 'tomorrow')

if __name__ == '__main__':
    unittest.main()
