import unittest
from unittest.mock import patch, MagicMock

from ..weather_fetcher.lambda_function import lambda_handler

class TestWeatherFetcherLambdaFunction(unittest.TestCase):
    @patch('src.lambda.weather_fetcher.lambda_function.boto3.client')
    @patch('src.lambda.weather_fetcher.lambda_function.requests.get')
    @patch('src.lambda.weather_fetcher.lambda_function.os.environ', {
        'WEATHER_API_SECRET_NAME': 'test-secret',
        'WEATHER_API_URL': 'https://api.testweather.com',
        'SQS_QUEUE_URL': 'https://sqs.testqueue.com',
        'TIMEOUT': '30'
    })
    def test_successful_weather_fetch(self, mock_requests_get, mock_boto3_client):
        mock_secrets_manager_client = MagicMock()
        mock_sqs_client = MagicMock()
        mock_boto3_client.side_effect = lambda service: (
            mock_secrets_manager_client if service == 'secretsmanager' else mock_sqs_client
        )

        mock_secrets_manager_client.get_secret_value.return_value = {'SecretString': 'test-api-key'}
        mock_weather_response = MagicMock()
        mock_weather_response.status_code = 200
        mock_weather_response.json.return_value = {'weather': 'sunny'}
        mock_weather_response.elapsed.total_seconds.return_value = 0.123
        mock_requests_get.return_value = mock_weather_response

        event = {
            'city_name': 'TestCity',
            'country_code': 'TC',
            'email': 'test@example.com',
            'phone_number': '1234567890',
            'notification_type': 'email'
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        expected_response = {
            'status_code': 200,
            'notification_type': 'email',
            'email': 'test@example.com',
            'phone_number': '1234567890',
            'city_name': 'TestCity',
            'data': {'weather': 'sunny'},
            'response_time_ms': 123
        }

        mock_sqs_client.send_message.assert_called_once()
        self.assertEqual(expected_response, response)


    @patch('src.lambda.weather_fetcher.lambda_function.boto3.client')
    @patch('src.lambda.weather_fetcher.lambda_function.requests.get')
    @patch('src.lambda.weather_fetcher.lambda_function.os.environ', {
        'WEATHER_API_SECRET_NAME': 'test-secret',
        'WEATHER_API_URL': 'https://api.testweather.com',
        'SQS_QUEUE_URL': 'https://sqs.testqueue.com',
        'TIMEOUT': '30'
    })
    def test_weather_fetch_failure(self, mock_requests_get, mock_boto3_client):
        mock_secrets_manager_client = MagicMock()
        mock_sqs_client = MagicMock()
        mock_boto3_client.side_effect = lambda service: (
            mock_secrets_manager_client if service == 'secretsmanager' else mock_sqs_client
        )

        mock_requests_get.side_effect = Exception('Weather API call failed')
        mock_secrets_manager_client.get_secret_value.return_value = {'SecretString': 'test-api-key'}

        event = {
            'city_name': 'TestCity',
            'country_code': 'TC',
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        expected_response = {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': '{"error": "Failed to fetch weather data", "details": "Weather API call failed"}'
        }

        self.assertEqual(expected_response, response)


    @patch('src.lambda.weather_fetcher.lambda_function.boto3.client')
    @patch('src.lambda.weather_fetcher.lambda_function.requests.get')
    @patch('src.lambda.weather_fetcher.lambda_function.os.environ', {
        'WEATHER_API_SECRET_NAME': 'test-secret',
        'WEATHER_API_URL': 'https://api.testweather.com',
        'SQS_QUEUE_URL': 'https://sqs.testqueue.com',
        'TIMEOUT': '30'
    })
    def test_missing_city_name(self, mock_requests_get, mock_boto3_client):
        mock_secrets_manager_client = MagicMock()
        mock_boto3_client.return_value = mock_secrets_manager_client

        event = {
            'country_code': 'TC'
        }
        context = MagicMock()

        response = lambda_handler(event, context)

        self.assertEqual(500, response['statusCode'])
        self.assertIn('Failed to fetch weather data', response['body'])
