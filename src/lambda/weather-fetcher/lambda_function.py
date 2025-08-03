import json
import boto3
import requests
import os
import logging
from datetime import datetime

log_level_name = os.environ.get('LOG_LEVEL', 'INFO')
log_level = getattr(logging, log_level_name.upper(), logging.INFO)
logger = logging.getLogger()
logger.setLevel(log_level)

def lambda_handler(event, context):
    """
    Weather Fetcher Lambda - Fetches weather data and sends to SQS
    """
    logger.info(f"Received event: {json.dumps(event)}")

    # Initialize AWS clients for secrets manager and SQS
    secrets_client = boto3.client('secretsmanager')
    sqs_client = boto3.client('sqs')

    try:
        # Get API key from Secrets Manager
        secret_name = os.environ['WEATHER_API_SECRET_NAME']
        response = secrets_client.get_secret_value(SecretId=secret_name)
        api_key = response['SecretString']

        # Extract city name and country code from the input event and form query parameters
        body = json.loads(event.get('body', '{}'))
        city_name = body.get('city_name')
        country_code = body.get('country_code')
        city = f"{city_name},{country_code}"
        query_params = {'q': city, 'appid': api_key}

        # Prepare request
        api_url = os.environ['WEATHER_API_URL']
        timeout = int(os.environ.get('TIMEOUT', '30'))

        logger.info(f"Making GET request to: {api_url}")

        weatherResponse = requests.get(api_url, params=query_params, timeout=timeout)
        weatherResponse.raise_for_status()
        response = {
            'status_code': weatherResponse.status_code,
            'data': weatherResponse.json(),
            'response_time_ms': int(weatherResponse.elapsed.total_seconds() * 1000)
        };

        # Prepare SQS request
        queue_url = os.environ['WEATHER_SQS_QUEUE_URL']
        sqs = boto3.client('sqs')
        sqs.send_message(
            QueueUrl = queue_url,
            MessageBody = json.dumps(response)
        )


        # Return weatherResponse and metadata
        return response;

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Failed to fetch weather data',
                'details': str(e)
            })
        }
